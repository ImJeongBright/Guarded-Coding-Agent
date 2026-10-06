import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from guarded_agent.approval import Approvals
from guarded_agent.gateway import Gateway

class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve(); self.work=self.base/'work'; self.work.mkdir()
        self.g=Gateway(self.work,self.base/'state')

    def test_protected_path_case_variants(self):
        for name in ['.GIT/config','.GuArD/policy.json','.AGENTS/a','.CODEX/a']:
            result=self.g.submit({'tool':'filesystem','operation':'write','path':name,'content':'bad'})
            self.assertEqual(result['decision'],'DENY',result)

    def test_shell_uppercase_secret_denied(self):
        (self.work/'.ENV').write_text('private')
        argv=[str(Path(sys.executable).resolve()),'-c','from pathlib import Path; print(Path(".ENV").read_text())']
        g=Gateway(self.work,self.base/'state2',{'version':'test','commands':[{'argv':argv}]})
        result=g.submit({'tool':'shell','operation':'exec','argv':argv})
        self.assertTrue(result['executed'],result)
        self.assertNotEqual(result['exit_code'],0,result)
        self.assertNotIn('private',result['stdout'])

    def test_approval_consumption_is_atomic(self):
        approvals=Approvals(self.base/'atomic')
        binding={'run':'same','action':'same'}
        pending=approvals.pending(binding,{'action':'same'},300); approvals.grant(pending)
        with ThreadPoolExecutor(max_workers=4) as pool:
            outcomes=list(pool.map(lambda _:approvals.consume(pending,binding),range(4)))
        self.assertEqual(sum(outcomes),1)

    def test_policy_binding_changed(self):
        approvals=Approvals(self.base/'atomic')
        pending=approvals.pending({'policy':'1'},{'action':'push'},300); approvals.grant(pending)
        self.assertFalse(approvals.consume(pending,{'policy':'2'}))

    def test_operator_cli_rejects_noninteractive_grant(self):
        state=self.base/'operator'; approvals=Approvals(state)
        pending=approvals.pending({'action':'push'},{'action':'push'},300)
        result=subprocess.run([sys.executable,'-m','guarded_agent','approve','--state',str(state),pending],input='approve\n',text=True,capture_output=True)
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(approvals.inspect(pending)['granted'])

    def test_local_remote_replacement_invalidates_approval(self):
        git=shutil.which('git'); remote=self.base/'remote.git'
        subprocess.run([git,'init','-b','feature/x',str(self.work)],capture_output=True,check=True)
        subprocess.run([git,'init','--bare',str(remote)],capture_output=True,check=True)
        subprocess.run([git,'-C',str(self.work),'remote','add','origin',str(remote)],check=True)
        g=Gateway(self.work,self.base/'git-state',{'version':'1','commands':[],'git_executable':git,'git_remotes':{'origin':str(remote)}})
        for request in [{'tool':'filesystem','operation':'write','path':'a','content':'a'},
                        {'tool':'git','operation':'add','paths':['a']},
                        {'tool':'git','operation':'commit','message':'a'}]:
            result=g.submit(request); self.assertEqual(result['exit_code'],0,result)
        request={'tool':'git','operation':'push','remote':'origin','branch':'feature/x'}
        pending=g.submit(request); self.assertEqual(pending['decision'],'REQUIRE_APPROVAL',pending)
        g.approvals.grant(pending['approval_id'])
        remote.rename(self.base/'previous.git')
        subprocess.run([git,'init','--bare',str(remote)],capture_output=True,check=True)
        result=g.submit(request,approval_id=pending['approval_id'])
        self.assertFalse(result['executed'],result)
        self.assertFalse((remote/'refs/heads/feature/x').exists())

    def test_exact_punctuation_profile_and_unlisted_command(self):
        argv=[str(Path(sys.executable).resolve()),'-c','print("one"); print("two")']
        g=Gateway(self.work,self.base/'punctuation',{'version':'1','commands':[{'argv':argv}]})
        result=g.submit({'tool':'shell','operation':'exec','argv':argv})
        self.assertEqual(result['exit_code'],0,result)
        result=g.submit({'tool':'shell','operation':'exec','argv':[argv[0],'-c','print("three"); print("four")']})
        self.assertFalse(result['executed'])

    def test_workspace_build_output_profile_can_precede_compile(self):
        binary=self.work/'build/future-binary'
        g=Gateway(self.work,self.base/'future',{'version':'1','commands':[{'argv':[str(binary)]}]})
        self.assertEqual(g.policy['commands'][0]['executable'],str(binary))

if __name__=='__main__':
    unittest.main()
