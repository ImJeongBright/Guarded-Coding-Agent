import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from guarded_agent.gateway import Gateway

class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.workspace=self.base/'work'; self.workspace.mkdir()
        self.g=Gateway(self.workspace,self.base/'state')

    def fs(self, op, path, **kw):
        return self.g.submit(dict(tool='filesystem',operation=op,path=path,**kw))

    def test_FS01_read_FS02_write(self):
        self.assertTrue(self.fs('write','src/a.c',content='int main(void){}')['executed'])
        self.assertEqual(self.fs('read','src/a.c')['stdout'],'int main(void){}')

    def test_FS03_traversal_and_nonexistent_target(self):
        result=self.fs('write','../../outside/new/a',content='no')
        self.assertEqual(result['matched_rule'],'FS-SCOPE')
        self.assertFalse((self.base/'outside').exists())

    def test_FS04_symlink_escape(self):
        (self.workspace/'escape').symlink_to(self.base,target_is_directory=True)
        self.assertFalse(self.fs('write','escape/secret',content='no')['executed'])
        self.assertFalse((self.base/'secret').exists())

    def test_inside_symlink_fail_closed(self):
        (self.workspace/'a').write_text('safe')
        (self.workspace/'b').symlink_to('a')
        self.assertEqual(self.fs('read','b')['matched_rule'],'FS-LINK')

    def test_hardlink_escape(self):
        external=self.base/'private'; external.write_text('secret')
        os.link(external,self.workspace/'linked')
        self.assertFalse(self.fs('write','linked',content='bad')['executed'])
        self.assertEqual(external.read_text(),'secret')

    def test_FS05_secrets_and_original_components(self):
        for path in ['.env','.env.local','.ssh/id_rsa','x.pem','credentials.json','.env/../a']:
            with self.subTest(path=path):
                self.assertEqual(self.fs('read',path)['decision'],'DENY')

    def test_FS06_protected_paths(self):
        for path in ['.guard/policy.json','.git/config','.agents/a','.codex/a']:
            self.assertEqual(self.fs('write',path,content='no')['matched_rule'],'FS-TRUSTED')

    def test_unicode_space_path_and_single_delete(self):
        path='소스 파일/a b.c'
        self.assertTrue(self.fs('write',path,content='hello')['executed'])
        self.assertTrue(self.fs('delete',path)['executed'])
        self.assertFalse(self.fs('delete','소스 파일')['executed'])

    def test_list_omits_protected_names(self):
        (self.workspace/'.env').write_text('fake')
        (self.workspace/'a').write_text('ok')
        self.assertEqual(self.fs('list','.')['stdout'],'a')

    def test_toctou_symlink_before_write(self):
        original=self.g.fs._execute
        def swapped(action):
            (self.workspace/'src').symlink_to(self.base,target_is_directory=True)
            return original(action)
        with patch.object(self.g.fs,'_execute',side_effect=swapped):
            self.assertFalse(self.fs('write','src/a',content='bad')['executed'])
        self.assertFalse((self.base/'a').exists())

    def test_AU01_decision_and_result_link(self):
        self.fs('write','a',content='test')
        events=[json.loads(line) for line in (self.base/'state/audit.jsonl').read_text().splitlines()]
        self.assertEqual([x['phase'] for x in events],['decision','result'])
        self.assertEqual(events[1]['parent'],events[0]['event_id'])

    def test_AU02_secret_content_and_result_redaction(self):
        fake='token=supersecretvalue sk-faketoken0123456789'
        self.fs('write','a',content=fake)
        result=self.fs('read','a')
        self.assertNotIn('supersecretvalue',result['stdout'])
        self.assertNotIn('faketoken',(self.base/'state/audit.jsonl').read_text())

    def test_audit_failure_stops_execution(self):
        with patch.object(self.g.audit,'record',side_effect=OSError('unavailable')):
            result=self.fs('write','a',content='no')
        self.assertEqual(result['matched_rule'],'AU-ERROR')
        self.assertFalse((self.workspace/'a').exists())

    def test_unknown_and_malformed_audited(self):
        for request in [{'tool':'unknown','operation':'x'},None,{'tool':'shell','operation':'exec','argv':'echo safe'}]:
            self.assertEqual(self.g.submit(request)['decision'],'DENY')

    def test_SH02_unknown_SH03_chaining_SH04_nested_SH05_redirect(self):
        for argv in [['rm','-rf','.'],['/usr/bin/true','&&','rm'],['/bin/sh','-c','true'],['echo','x','>','../a']]:
            self.assertFalse(self.g.submit({'tool':'shell','operation':'exec','argv':argv})['executed'])

    def test_state_must_be_external(self):
        with self.assertRaises(ValueError):
            Gateway(self.workspace,self.workspace/'state')

    def test_policy_change_stops_action(self):
        policy=self.base/'profile.json'
        policy.write_text(json.dumps({'version':'1','commands':[]}))
        g=Gateway(self.workspace,self.base/'state2',policy_path=policy)
        policy.write_text(json.dumps({'version':'2','commands':[]}))
        self.assertEqual(g.submit({'tool':'filesystem','operation':'write','path':'a','content':'no'})['matched_rule'],'AP-BINDING')

    def test_fifo_does_not_block(self):
        os.mkfifo(self.workspace/'pipe')
        self.assertFalse(self.fs('read','pipe')['executed'])

if __name__=='__main__':
    unittest.main()
