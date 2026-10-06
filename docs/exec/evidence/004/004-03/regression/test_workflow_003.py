"""003 capability regressions: ordinary workflow and adversarial boundaries."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from guarded_agent.gateway import Gateway
from guarded_agent.mcp import descriptors


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.work = self.base/'work'; self.work.mkdir()
        (self.work/'src').mkdir()
        self.file = self.work/'src/a.txt'
        self.file.write_text('first\nunique line\nlast\n')
        self.g = Gateway(self.work, self.base/'state')

    def fs(self, operation, path='src/a.txt', **data):
        return self.g.submit(dict(tool='filesystem', operation=operation, path=path, **data))

    def edit(self, **data):
        request = dict(old_text='unique line', new_text='changed line',
                       expected_sha256=hashlib.sha256(self.file.read_bytes()).hexdigest())
        return self.fs('edit', **(request | data))

    def test_read_range_hash_and_bounds(self):
        result = self.fs('read', start_line=2, end_line=2)
        self.assertEqual(result['stdout'], 'unique line\n')
        self.assertEqual(result['sha256'], hashlib.sha256(self.file.read_bytes()).hexdigest())
        self.assertEqual(result['total_lines'], 3)
        for data in [dict(start_line=0), dict(end_line=2), dict(start_line=True),
                     dict(start_line=1, end_line=502), dict(start_line=3, end_line=2)]:
            self.assertEqual(self.fs('read', **data)['decision'], 'DENY')

    def test_search_literal_recursive_and_hidden_paths(self):
        (self.work/'.env').write_text('unique hidden')
        (self.work/'.git').mkdir(); (self.work/'.git/hidden').write_text('unique hidden')
        (self.work/'src/link').symlink_to(self.file)
        (self.work/'src/binary').write_bytes(b'\0unique')
        result = self.fs('search', '.', query='unique', glob='*.txt')
        self.assertEqual(result['matches'], [dict(path='src/a.txt', line=2, text='unique line')])
        self.assertFalse(result['truncated'])
        self.assertEqual(self.fs('search', '.', query='.*')['matches'], [])
        for path in ['../outside', '.env', '.git', 'src/link']:
            self.assertEqual(self.fs('search', path, query='unique')['decision'], 'DENY')

    def test_search_hardlinks_and_result_bound(self):
        outside = self.base/'outside'; outside.write_text('private marker')
        os.link(outside, self.work/'src/hard')
        self.assertEqual(self.fs('search', '.', query='private')['matches'], [])
        self.file.write_text('match\n'*250)
        result = self.fs('search', '.', query='match')
        self.assertEqual(len(result['matches']), 200)
        self.assertTrue(result['truncated'])

    def test_empty_query_lists_only_bounded_ordinary_file_names(self):
        (self.work/'src/.env').write_text('private')
        (self.work/'src/linked.txt').symlink_to(self.file)
        result = self.fs('search','.',query='',glob='*.txt')
        self.assertEqual(result['decision'],'ALLOW')
        self.assertEqual(result['matches'],[{'path':'src/a.txt'}])
        self.assertEqual(result['scanned_bytes'],0)

    def test_edit_atomic_mode_and_audit_omits_text(self):
        self.file.chmod(0o644)
        old_inode = self.file.stat().st_ino
        result = self.edit()
        self.assertTrue(result['executed'])
        self.assertEqual(self.file.read_text(), 'first\nchanged line\nlast\n')
        self.assertNotEqual(self.file.stat().st_ino, old_inode)
        self.assertEqual(self.file.stat().st_mode & 0o777, 0o644)
        audit = (self.base/'state/audit.jsonl').read_text()
        self.assertNotIn('unique line', audit); self.assertNotIn('changed line', audit)
        self.assertEqual(list((self.work/'src').glob('.guard-edit-*')), [])

    def test_edit_stale_ambiguous_missing_and_size(self):
        for data in [dict(expected_sha256='0'*64), dict(old_text='first', new_text='x'*1_000_000),
                     dict(old_text='absent'), dict(old_text=''), dict(expected_sha256='invalid')]:
            before = self.file.read_bytes()
            self.assertEqual(self.edit(**data)['decision'], 'DENY')
            self.assertEqual(self.file.read_bytes(), before)
        self.file.write_text('unique line\nunique line\n')
        self.assertEqual(self.edit()['decision'], 'DENY')

    def test_edit_change_after_decision_does_not_overwrite(self):
        original = self.g.fs._execute
        def changed(action):
            self.file.write_text('external change\n')
            return original(action)
        with patch.object(self.g.fs, '_execute', side_effect=changed):
            self.assertEqual(self.edit()['matched_rule'], 'FS-STALE')
        self.assertEqual(self.file.read_text(), 'external change\n')

    def test_edit_link_swap_does_not_touch_outside(self):
        outside = self.base/'outside'; outside.write_text('private')
        original = self.g.fs._execute
        def changed(action):
            self.file.unlink(); self.file.symlink_to(outside)
            return original(action)
        with patch.object(self.g.fs, '_execute', side_effect=changed):
            self.assertEqual(self.edit()['decision'], 'DENY')
        self.assertEqual(outside.read_text(), 'private')

    def test_edit_replace_failure_leaves_original_and_no_temp(self):
        before=self.file.read_bytes()
        with patch('guarded_agent.filesystem.os.replace',side_effect=OSError('replacement failed')):
            result=self.edit()
        self.assertEqual(result['decision'],'DENY')
        self.assertEqual(self.file.read_bytes(),before)
        self.assertEqual(list((self.work/'src').glob('.guard-edit-*')),[])

    def test_edit_temp_collision_never_deletes_preexisting_file(self):
        collision=self.work/'src/.guard-edit-collision'; collision.write_text('keep this unrelated file')
        before=self.file.read_bytes()
        with patch('guarded_agent.filesystem.uuid.uuid4',return_value=SimpleNamespace(hex='collision')):
            result=self.edit()
        self.assertEqual(result['decision'],'DENY')
        self.assertEqual(self.file.read_bytes(),before)
        self.assertTrue(collision.exists())
        self.assertEqual(collision.read_text(),'keep this unrelated file')

    def test_search_link_swap_after_validation_is_not_read(self):
        outside=self.base/'outside'; outside.write_text('private marker')
        relative=self.g.fs.relative
        def swapped(raw):
            result=relative(raw)
            if raw=='src/a.txt':
                self.file.unlink(); self.file.symlink_to(outside)
            return result
        with patch.object(self.g.fs,'relative',side_effect=swapped):
            result=self.fs('search','.',query='private')
        self.assertEqual(result['matches'],[])
        self.assertEqual(outside.read_text(),'private marker')

    def test_phase_timings_have_real_execution_component(self):
        result = self.fs('read')
        timings = result['timings_ms']
        self.assertGreater(timings['execution'], 0)
        self.assertGreater(timings['audit'], 0)
        self.assertGreaterEqual(timings['total'], sum(timings[key] for key in
            ('normalization', 'decision', 'audit', 'execution')))
        denied = self.fs('read', '../outside')
        self.assertEqual(denied['timings_ms']['execution'], 0)

    def test_mcp_schema_types_and_new_operations(self):
        tools = {tool['name']:tool for tool in descriptors(self.g)}
        ops = {x['properties']['operation']['const']:x for x in tools['guard_filesystem']['inputSchema']['oneOf']}
        self.assertIn('edit', ops); self.assertIn('search', ops)
        self.assertEqual(ops['read']['properties']['start_line']['type'], 'integer')
        self.assertEqual(ops['search']['properties']['exclude_dirs']['maxItems'], 32)
        self.assertIn('exact exclude_dirs', tools['guard_filesystem']['description'])
        git_ops = {x['properties']['operation']['const']:x for x in tools['guard_git']['inputSchema']['oneOf']}
        self.assertEqual(git_ops['diff']['properties']['staged']['type'], 'boolean')


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.work = self.base/'work'; self.work.mkdir()
        (self.work/'test').mkdir(); (self.work/'test/a.test.mjs').write_text("import test from 'node:test'; test('alpha',()=>{}); test('beta',()=>{});\n")
        (self.work/'package.json').write_text(json.dumps({'scripts': {'test': 'node --test test/*.test.mjs'}}))
        self.node = str(Path(shutil.which('node')).resolve())
        self.policy = {'version':'003', 'commands':[{'id':'tests','argv':[self.node,'--test','test/*.test.mjs'],
            'variants':{'repeat':[self.node,'--test','test/*.test.mjs']},
            'filter':{'kind':'node-test-literal','position':2}}]}
        self.g = Gateway(self.work, self.base/'state', self.policy)

    def test_named_mode_and_literal_test_filter(self):
        for data in [dict(profile='tests'), dict(profile='tests', mode='repeat'), dict(profile='tests', filter='alpha')]:
            result = self.g.submit(dict(tool='shell',operation='run',**data))
            self.assertTrue(result['executed'], result)
            self.assertEqual(result['exit_code'], 0)
        filtered = self.g.submit(dict(tool='shell',operation='run',profile='tests',filter='alpha'))
        self.assertIn('alpha', filtered['stdout']); self.assertNotIn('✔ beta', filtered['stdout'])

    def test_unknown_modes_and_filter_syntax_fail_closed(self):
        for data in [dict(profile='absent'), dict(profile='tests',mode='unknown'),
                     *[dict(profile='tests',filter=s) for s in ['.*','--inspect','../a','a\nb','$(id)','a|b','']]]:
            self.assertEqual(self.g.submit(dict(tool='shell',operation='run',**data))['decision'], 'DENY')
        self.assertEqual(self.g.submit(dict(tool='shell',operation='exec',argv=[self.node,'--test','--inspect','test/*.test.mjs']))['decision'], 'DENY')

    def test_exec_recognizes_only_fixed_variant_and_literal_filter(self):
        request=dict(tool='shell',operation='exec',argv=[self.node,'--test','--test-name-pattern','alpha','test/*.test.mjs'])
        result=self.g.submit(request)
        self.assertEqual(result['exit_code'],0,result)
        self.assertIn('alpha',result['stdout']); self.assertNotIn('✔ beta',result['stdout'])
        for argv in [[self.node,'--test','--test-name-pattern','.*','test/*.test.mjs'],
                     [self.node,'--test','--test-name-pattern','alpha','test/*.test.mjs','--inspect'],
                     [self.node,'--test','--test-name-pattern','alpha','../outside.mjs']]:
            self.assertEqual(self.g.submit(dict(tool='shell',operation='exec',argv=argv))['decision'],'DENY')

    def test_agent_cannot_discover_apply_or_edit_operator_state(self):
        for request in [dict(tool='shell',operation='discover'),dict(tool='shell',operation='profile-apply'),
                        dict(tool='filesystem',operation='write',path=str(self.base/'state/policy.json'),content='{}')]:
            self.assertEqual(self.g.submit(request)['decision'],'DENY')

    def test_candidate_file_tampering_and_unknown_id_rejected(self):
        from guarded_agent.profiles import discover,apply_candidates
        state=self.base/'candidate'; candidate=discover(self.work,state)
        with self.assertRaises(ValueError): apply_candidates(self.work,state,candidate['digest'],['unknown'])
        data=json.loads((state/'profile-candidates.json').read_text())
        data['commands'][0]['argv']=[self.node,'--require','./evil.mjs','--test']
        (state/'profile-candidates.json').write_text(json.dumps(data))
        with self.assertRaises(ValueError): apply_candidates(self.work,state,candidate['digest'],['node-tests'])
        self.assertFalse((state/'policy.json').exists())

    def test_discovery_no_execution_and_reviewed_apply(self):
        from guarded_agent.profiles import discover, apply_candidates
        real_run = subprocess.run
        def metadata_only(argv, **kwargs):
            self.assertEqual(argv, ['/usr/bin/xcrun','--find','git'])
            return real_run(argv, **kwargs)
        with patch('subprocess.run', side_effect=metadata_only):
            candidates = discover(self.work, self.base/'discover-state')
        self.assertEqual([x['id'] for x in candidates['commands']], ['node-tests'])
        state = self.base/'discover-state'
        apply_candidates(self.work, state, candidates['digest'], ['node-tests'])
        g = Gateway(self.work, state, policy_path=state/'policy.json')
        self.assertEqual(g.submit(dict(tool='shell',operation='run',profile='node-tests',filter='alpha'))['exit_code'], 0)

    def test_manifest_scripts_are_suggestions_only(self):
        from guarded_agent.profiles import discover
        for script in ['node --test test/*.test.mjs; touch marker', 'npm install && node --test', 'node --require ./evil.mjs --test']:
            (self.work/'package.json').write_text(json.dumps({'scripts':{'test':script}}))
            candidates = discover(self.work, self.base/('state-'+str(len(script))))
            self.assertEqual(candidates['commands'], [])
        self.assertFalse((self.work/'marker').exists())

    def test_candidate_binding_rejects_stale_and_tampered(self):
        from guarded_agent.profiles import discover, apply_candidates
        state = self.base/'binding'; candidates = discover(self.work,state)
        for digest in ['0'*64, candidates['digest']]:
            if digest == candidates['digest']: (self.work/'package.json').write_text('{}')
            with self.assertRaises(ValueError): apply_candidates(self.work,state,digest,['node-tests'])
        self.assertFalse((state/'policy.json').exists())

    def test_policy_update_requires_session_restart(self):
        from guarded_agent.profiles import discover, apply_candidates
        state = self.base/'update'; state.mkdir()
        (state/'policy.json').write_text(json.dumps({'version':'before','commands':[]}))
        old = Gateway(self.work,state,policy_path=state/'policy.json')
        candidates = discover(self.work,state)
        apply_candidates(self.work,state,candidates['digest'],['node-tests'])
        result = old.submit(dict(tool='filesystem',operation='write',path='marker',content='x'))
        self.assertEqual(result['matched_rule'],'AP-BINDING'); self.assertFalse((self.work/'marker').exists())
        fresh = Gateway(self.work,state,policy_path=state/'policy.json')
        self.assertEqual(fresh.submit(dict(tool='shell',operation='run',profile='node-tests'))['exit_code'],0)

    def test_profile_cannot_change_executable_or_write_root(self):
        for change in [dict(variants={'bad':['/bin/sh','-c','true']}),dict(write_paths=['.']),
                       dict(filter={'kind':'arbitrary','position':2}),dict(id='../../x')]:
            policy = {'version':'test','commands':[self.policy['commands'][0] | change]}
            with self.assertRaises(ValueError): Gateway(self.work,self.base/'invalid',policy)


if __name__ == '__main__':
    unittest.main()
