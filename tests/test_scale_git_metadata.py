"""04-01 scale regression: internal Git metadata is not user-visible output."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from guarded_agent.domain import MAX_GIT_METADATA_OUTPUT, MAX_OUTPUT
from guarded_agent.filesystem import Blocked
from guarded_agent.gateway import Gateway
from guarded_agent.git import resolve_executable


class GitMetadataScaleTests(unittest.TestCase):
    FILE_COUNT=2_000

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='guard-git-metadata-scale-')
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve()
        self.work=self.base/'work'; self.work.mkdir()
        self.git=resolve_executable('/usr/bin/git')
        self.path='src/module_000/subsystem_000/shared_component_source_00000.c'
        (self.work/'src/module_000/subsystem_000').mkdir(parents=True)
        for index in range(self.FILE_COUNT):
            path=self.work/f'src/module_000/subsystem_000/shared_component_source_{index:05}.c'
            path.write_text(f'int source_{index:05} = 0;\n')
        self.raw('init','-b','feature/scale-metadata')
        self.raw('--literal-pathspecs','add','--','src')
        self.raw('-c','user.name=Scale Fixture','-c','user.email=scale@example.invalid',
                 '-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false',
                 'commit','-m','Baseline for metadata scale regression')
        self.gateway=Gateway(self.work,self.base/'operator-state')
        self.paths=self.raw('ls-files','-z').split(b'\0')[:-1]
        self.path=self.paths[-1].decode() if self.paths[-1].endswith(b'.c') else self.paths[-2].decode()

    def raw(self,*args):
        return subprocess.run([self.git,'-C',str(self.work),*args],check=True,capture_output=True).stdout

    def request(self,operation,**fields):
        return self.gateway.submit({'tool':'git','operation':operation,**fields})

    def test_complete_hidden_metadata_passes_large_repository_git_flow(self):
        raw_paths=self.raw('ls-files','-z')
        self.assertGreater(len(raw_paths),MAX_OUTPUT)
        self.assertLess(len(raw_paths),MAX_GIT_METADATA_OUTPUT)

        changed=self.work/self.path
        changed.write_text(changed.read_text().replace('= 0;','= 1;'))
        status=self.request('status')
        self.assertEqual((status['decision'],status['exit_code']),('ALLOW',0),status)
        diff=self.request('diff',paths=[self.path])
        self.assertEqual((diff['decision'],diff['exit_code']),('ALLOW',0),diff)
        self.assertIn('+int source_',diff['stdout'])
        self.assertLessEqual(len(diff['stdout'].encode()),MAX_OUTPUT)

        staged=self.request('add',paths=[self.path])
        self.assertEqual((staged['decision'],staged['exit_code']),('ALLOW',0),staged)
        reviewed=self.request('diff',staged=True,paths=[self.path])
        self.assertEqual((reviewed['decision'],reviewed['exit_code']),('ALLOW',0),reviewed)
        committed=self.request('commit',message='Change one file in the large index')
        self.assertEqual((committed['decision'],committed['exit_code']),('ALLOW',0),committed)
        clean=self.request('status')
        self.assertEqual((clean['decision'],clean['stdout']),('ALLOW',''),clean)

        (self.work/'.env').write_text('SCALE_FIXTURE=DUMMY_METADATA_SECRET\n')
        self.raw('--literal-pathspecs','add','--','.env')
        self.raw('-c','user.name=Scale Fixture','-c','user.email=scale@example.invalid',
                 '-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false',
                 'commit','-m','Add fake sensitive file for review regression')
        self.raw('rm','--cached','--','.env')
        secret=self.request('diff',staged=True)
        self.assertEqual((secret['decision'],secret['matched_rule'],secret['executed']),
                         ('DENY','FS-SENSITIVE',False),secret)
        self.assertNotIn('DUMMY_METADATA_SECRET',str(secret))
        audit=(self.base/'operator-state/audit.jsonl').read_text()
        self.assertNotIn('DUMMY_METADATA_SECRET',audit)

    def test_metadata_overflow_still_denies_before_execution(self):
        def incomplete(argv,cwd,workspace,**kwargs):
            self.assertIn('ls-files',argv)
            self.assertEqual(kwargs.get('output_limit'),MAX_GIT_METADATA_OUTPUT)
            return {'exit_code':0,'stdout':'safe.c\0','stderr':'','output_truncated':True}
        with patch('guarded_agent.git.sandbox.run',side_effect=incomplete), \
             patch.object(self.gateway.git,'_execute',side_effect=AssertionError('must not execute')) as execute:
            result=self.request('status')
        self.assertEqual(result['matched_rule'],'GT-STATE',result)
        self.assertFalse(result['executed'],result)
        execute.assert_not_called()

    def test_metadata_path_count_overflow_still_denies(self):
        with patch('guarded_agent.git.MAX_GIT_PATHS',2), \
             patch.object(self.gateway.git,'_query',return_value='one.c\0two.c\0three.c\0'):
            with self.assertRaises(Blocked) as caught:
                self.gateway.git._state_paths('ls-files','-z')
        self.assertEqual(caught.exception.rule,'GT-STATE')

    def test_metadata_path_lexical_validation_preserves_scope_and_sensitivity(self):
        valid='src/space here-한글.c\0'
        with patch.object(self.gateway.git,'_query',return_value=valid):
            self.assertEqual(self.gateway.git._state_paths('ls-files','-z'),
                             ['src/space here-한글.c'])

        for path in ('/outside.c','./src/a.c','src//a.c','src/../a.c','src/a.c/',
                     'x'*4097,'src/bad\ufffdname.c'):
            with self.subTest(path=path[:40]), patch.object(
                    self.gateway.git,'_query',return_value=path+'\0'):
                with self.assertRaises(Blocked) as caught:
                    self.gateway.git._state_paths('ls-files','-z')
                self.assertEqual(caught.exception.rule,'GT-STATE')

        for path, rule in (('.env','FS-SENSITIVE'),('.git/config','FS-TRUSTED')):
            with self.subTest(path=path), patch.object(
                    self.gateway.git,'_query',return_value=path+'\0'):
                with self.assertRaises(Blocked) as caught:
                    self.gateway.git._state_paths('ls-files','-z')
                self.assertEqual(caught.exception.rule,rule)

    def test_link_added_during_metadata_lookup_is_caught_before_git_execution(self):
        outside=self.base/'outside.c'
        outside.write_text('outside\n')
        late_link=self.work/'late-link.c'
        original=self.gateway.git._query

        def inject(*args,**kwargs):
            if args==('ls-files','-z'):
                os.symlink(outside,late_link)
                return 'src/module_000/subsystem_000/shared_component_source_00000.c\0'
            return original(*args,**kwargs)

        try:
            with patch.object(self.gateway.git,'_query',side_effect=inject), \
                 patch.object(self.gateway.git,'_execute',side_effect=AssertionError(
                     'Git executor ran after a late workspace symlink')) as execute:
                result=self.request('status')
            self.assertEqual((result['decision'],result['matched_rule'],result['executed']),
                             ('DENY','FS-LINK',False),result)
            execute.assert_not_called()
        finally:
            late_link.unlink(missing_ok=True)


if __name__=='__main__':
    unittest.main()
