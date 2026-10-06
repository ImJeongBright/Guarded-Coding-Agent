import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from guarded_agent.gateway import Gateway
from guarded_agent.sandbox import SandboxUnavailable

class ShellGitTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name); self.work=self.base/'work'; self.work.mkdir()
        self.git=shutil.which('git')
        self.command=[str(Path(sys.executable).resolve()),'-c','print("guarded")']
        self.policy={'version':'001','commands':[{'argv':self.command}], 'git_executable':self.git,'git_remotes':{}}
        self.g=Gateway(self.work,self.base/'state',self.policy,run_id='test-run')

    def shell(self, argv, **kw):
        return self.g.submit(dict(tool='shell',operation='exec',argv=argv,**kw))

    def git_request(self, op, **kw):
        return self.g.submit(dict(tool='git',operation=op,**kw))

    def init_repo(self):
        subprocess.run([self.git,'init','-b','feature/x',str(self.work)],check=True,capture_output=True)
        (self.work/'a.c').write_text('int a;\n')

    def test_SH01_exact_profile_execution(self):
        result=self.shell(self.command)
        self.assertTrue(result['executed'],result)
        self.assertEqual(result['exit_code'],0,result)
        self.assertEqual(result['stdout'].strip(),'guarded')

    def test_profile_argument_cwd_and_shadow_rejected(self):
        self.assertFalse(self.shell(self.command+['extra'])['executed'])
        (self.work/'sub').mkdir()
        self.assertFalse(self.shell(self.command,cwd='sub')['executed'])
        self.assertFalse(self.shell(['python3','-c','print("guarded")'])['executed'])

    def test_nested_sandbox_fails_closed(self):
        with patch('guarded_agent.shell.sandbox.run',side_effect=SandboxUnavailable('offline')):
            result=self.shell(self.command)
        self.assertEqual(result['matched_rule'],'SH-SANDBOX')
        self.assertFalse(result['executed'])

    def sandbox_probe(self, source):
        command=[str(Path(sys.executable).resolve()),'-c',source]
        policy={'version':'probe','commands':[{'argv':command}],'git_remotes':{}}
        g=Gateway(self.work,self.base/'probe-state',policy)
        return g.submit({'tool':'shell','operation':'exec','argv':command})

    def test_sandbox_denies_outside_read_write(self):
        outside=self.base/'outside'; outside.write_text('private')
        source=f'from pathlib import Path; print(Path({str(outside)!r}).read_text())'
        result=self.sandbox_probe(source)
        self.assertTrue(result['executed'],result)
        self.assertNotEqual(result['exit_code'],0,result)
        self.assertNotIn('private',result['stdout'])
        target=self.base/'escape'
        result=self.sandbox_probe(f'from pathlib import Path; Path({str(target)!r}).write_text("bad")')
        self.assertTrue(result['executed'],result)
        self.assertNotEqual(result['exit_code'],0,result)
        self.assertFalse(target.exists())

    def test_sandbox_denies_secret_and_state(self):
        (self.work/'.env').write_text('private')
        result=self.sandbox_probe('from pathlib import Path; print(Path(".env").read_text())')
        self.assertTrue(result['executed'],result)
        self.assertNotEqual(result['exit_code'],0,result)
        target=self.base/'probe-state/audit.jsonl'
        result=self.sandbox_probe(f'from pathlib import Path; Path({str(target)!r}).write_text("bad")')
        self.assertTrue(result['executed'],result)
        self.assertNotEqual(result['exit_code'],0,result)
        self.assertTrue(target.read_text().startswith('{'))

    def test_sandbox_denies_network(self):
        result=self.sandbox_probe('import socket; s=socket.socket(); s.bind(("127.0.0.1", 0))')
        self.assertTrue(result['executed'],result)
        self.assertNotEqual(result['exit_code'],0,result)

    def test_timeout(self):
        command=['/bin/sleep','2']
        g=Gateway(self.work,self.base/'timeout',{'version':'t','commands':[{'argv':command,'timeout':0.05}]})
        result=g.submit({'tool':'shell','operation':'exec','argv':command})
        self.assertEqual(result['exit_code'],124,result)

    def test_GT01_status_GT02_diff_GT03_commit(self):
        self.init_repo()
        self.assertEqual(self.git_request('status')['exit_code'],0)
        self.assertEqual(self.git_request('diff')['exit_code'],0)
        self.assertEqual(self.git_request('add',paths=['a.c'])['exit_code'],0)
        result=self.git_request('commit',message='Add C source')
        self.assertEqual(result['exit_code'],0,result)
        self.assertIn('Add C source',self.git_request('log')['stdout'])

    def test_git_hook_not_executed(self):
        self.init_repo()
        hook=self.work/'.git/hooks/pre-commit'
        hook.write_text('#!/bin/sh\ntouch hook-ran\n'); hook.chmod(0o755)
        self.assertEqual(self.git_request('add',paths=['a.c'])['exit_code'],0)
        result=self.git_request('commit',message='Skip untrusted hooks')
        self.assertEqual(result['exit_code'],0,result)
        self.assertFalse((self.work/'hook-ran').exists())

    def test_staged_diff_reviews_only_index(self):
        self.init_repo()
        self.assertEqual(self.git_request('add',paths=['a.c'])['exit_code'],0)
        (self.work/'a.c').write_text('int b;\n')
        staged=self.git_request('diff',staged=True)
        self.assertEqual(staged['exit_code'],0,staged)
        self.assertIn('+int a;',staged['stdout']); self.assertNotIn('+int b;',staged['stdout'])
        unstaged=self.git_request('diff',paths=['a.c'])
        self.assertIn('+int b;',unstaged['stdout'])

    def test_git_no_system_cache_or_attributes_diagnostics(self):
        self.init_repo()
        result=self.git_request('status')
        self.assertEqual(result['exit_code'],0,result)
        self.assertNotIn('xcrun_db',result['stderr'])
        self.assertNotIn('/etc/gitattributes',result['stderr'])
        self.assertEqual(result['stderr'],'',result)

    def test_git_executable_config_and_attributes_denied(self):
        self.init_repo()
        config=self.work/'.git/config'
        config.write_text(config.read_text()+'\n[core]\n\tsshCommand = touch bad\n')
        self.assertEqual(self.git_request('status')['decision'],'DENY')

    def test_git_sensitive_tracked_file_denied(self):
        self.init_repo()
        (self.work/'.env').write_text('fake')
        subprocess.run([self.git,'-C',str(self.work),'add','.env'],check=True)
        self.assertEqual(self.git_request('diff')['decision'],'DENY')

    def test_truncated_git_state_query_stops_before_executor(self):
        self.init_repo()
        incomplete={'exit_code':0,'stdout':'a.c\0','stderr':'','output_truncated':True}
        with patch('guarded_agent.git.sandbox.run',return_value=incomplete), patch.object(
                self.g.git,'_execute',side_effect=AssertionError('Incomplete state reached executor')) as execute:
            result=self.git_request('diff')
        self.assertEqual(result['matched_rule'],'GT-STATE')
        execute.assert_not_called()

    def test_git_add_dot_and_destructive_unknown(self):
        self.init_repo()
        self.assertEqual(self.git_request('add',paths=['.'])['matched_rule'],'GT-PATHS')
        self.assertFalse(self.git_request('reset',hard=True)['executed'])

    def setup_push(self):
        self.init_repo()
        remote=self.base/'remote.git'
        subprocess.run([self.git,'init','--bare',str(remote)],check=True,capture_output=True)
        subprocess.run([self.git,'-C',str(self.work),'remote','add','origin',str(remote)],check=True)
        policy={**self.policy,'git_remotes':{'origin':str(remote)}}
        self.g=Gateway(self.work,self.base/'state',policy,run_id='test-run')
        self.assertEqual(self.git_request('add',paths=['a.c'])['exit_code'],0)
        self.assertEqual(self.git_request('commit',message='Initial') ['exit_code'],0)
        return remote

    def test_GT04_AP01_exact_approval_push(self):
        remote=self.setup_push()
        request={'tool':'git','operation':'push','remote':'origin','branch':'feature/x'}
        pending=self.g.submit(request)
        self.assertEqual(pending['decision'],'REQUIRE_APPROVAL',pending)
        self.assertFalse((remote/'refs/heads/feature/x').exists())
        self.g.approvals.grant(pending['approval_id'])  # Trusted operator fixture, never an agent tool.
        result=self.g.submit(request,approval_id=pending['approval_id'])
        self.assertEqual(result['exit_code'],0,result)
        self.assertTrue((remote/'refs/heads/feature/x').exists())
        self.assertEqual(self.g.submit(request,approval_id=pending['approval_id'])['matched_rule'],'AP-INVALID')

    def test_GT05_force_push_denied(self):
        self.setup_push()
        result=self.git_request('push',remote='origin',branch='feature/x',force=True)
        self.assertEqual(result['matched_rule'],'GT-DESTRUCTIVE')

    def test_AP02_changed_branch_AP04_other_run(self):
        self.setup_push()
        request={'tool':'git','operation':'push','remote':'origin','branch':'feature/x'}
        pending=self.g.submit(request); self.g.approvals.grant(pending['approval_id'])
        altered={**request,'branch':'feature/y'}
        self.assertFalse(self.g.submit(altered,approval_id=pending['approval_id'])['executed'])
        another=Gateway(self.work,self.base/'state',self.g.policy,run_id='other')
        self.assertEqual(another.submit(request,approval_id=pending['approval_id'])['matched_rule'],'AP-INVALID')

    def test_AP03_expired(self):
        self.setup_push()
        request={'tool':'git','operation':'push','remote':'origin','branch':'feature/x'}
        pending=self.g.submit(request); self.g.approvals.grant(pending['approval_id'])
        with self.g.approvals.connect() as connection:
            connection.execute('UPDATE approvals SET expires=0 WHERE id=?',(pending['approval_id'],))
        self.assertEqual(self.g.submit(request,approval_id=pending['approval_id'])['matched_rule'],'AP-INVALID')

    def test_head_change_invalidates_approval(self):
        self.setup_push()
        request={'tool':'git','operation':'push','remote':'origin','branch':'feature/x'}
        pending=self.g.submit(request); self.g.approvals.grant(pending['approval_id'])
        self.g.submit({'tool':'filesystem','operation':'write','path':'a.c','content':'int b;\n'})
        self.git_request('add',paths=['a.c']); self.git_request('commit',message='Changed HEAD')
        self.assertEqual(self.g.submit(request,approval_id=pending['approval_id'])['matched_rule'],'AP-INVALID')

    def test_profile_version_change_invalidates_approval(self):
        self.setup_push()
        request={'tool':'git','operation':'push','remote':'origin','branch':'feature/x'}
        pending=self.g.submit(request); self.g.approvals.grant(pending['approval_id'])
        fresh=Gateway(self.work,self.base/'state',{**self.g.policy,'version':'003-new'},run_id='test-run')
        self.assertEqual(fresh.submit(request,approval_id=pending['approval_id'])['matched_rule'],'AP-INVALID')

if __name__=='__main__':
    unittest.main()
