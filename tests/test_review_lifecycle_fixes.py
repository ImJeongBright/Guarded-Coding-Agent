"""R003 process lifetime and R002 transport outcome regressions."""
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from guarded_agent.gateway import Gateway
from guarded_agent.host import capture
from guarded_agent.mcp import Server
from guarded_agent.process_lifecycle import ProcessScope, LifecycleUnavailable, _UniqueInfo, _AuditToken, _backend


class ReviewLifecycleFixTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='guard-lifecycle-fix-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.work = self.base/'work'; self.work.mkdir(); (self.work/'output').mkdir()
        self.python = str(Path(sys.executable).resolve())

    def run_source(self, source, *, timeout=2):
        argv = [self.python, '-B', '-c', source]
        gateway = Gateway(self.work, self.base/'state', {'version':'lifecycle-test',
            'commands':[{'argv':argv,'timeout':timeout,'write_paths':['output']}]})
        result = gateway.submit(dict(tool='shell',operation='exec',argv=argv))
        self.assertTrue(result['executed'], result)
        self.assertEqual(result.get('lifecycle_status'),'terminated', result)
        return result

    def assert_no_late_write(self, result):
        self.assertFalse((self.work/'output/late-marker').exists(), result)
        time.sleep(0.4)
        self.assertFalse((self.work/'output/late-marker').exists(), result)
        self.assertGreaterEqual(result['terminated_scope_processes'],1,result)

    def test_detached_child_normal_return_is_terminated(self):
        child='import time;from pathlib import Path;time.sleep(0.25);Path("output/late-marker").write_text("fixture")'
        source=f'import subprocess,sys; p=subprocess.Popen([sys.executable,"-c",{child!r}],start_new_session=True);print(p.pid)'
        result=self.run_source(source)
        self.assertEqual(result['exit_code'],0,result)
        self.assert_no_late_write(result)

    def test_detached_child_timeout_is_terminated(self):
        child='import time;from pathlib import Path;time.sleep(0.3);Path("output/late-marker").write_text("fixture")'
        source=f'import subprocess,sys,time;p=subprocess.Popen([sys.executable,"-c",{child!r}],start_new_session=True);print(p.pid,flush=True);time.sleep(1)'
        result=self.run_source(source,timeout=0.08)
        self.assertEqual(result['exit_code'],124,result)
        self.assertTrue(result['timed_out'],result)
        self.assert_no_late_write(result)

    def test_posix_spawn_group_escape_is_terminated(self):
        child='import time;from pathlib import Path;time.sleep(0.25);Path("output/late-marker").write_text("fixture")'
        result=self.run_source(f'import os,sys;print(os.posix_spawn(sys.executable,[sys.executable,"-c",{child!r}],os.environ,setpgroup=0))')
        self.assertEqual(result['exit_code'],0,result)
        self.assert_no_late_write(result)

    def test_reparented_double_fork_grandchild_is_terminated(self):
        source='''import os,time
from pathlib import Path
r,w=os.pipe(); first=os.fork()
if first:
 os.close(w);os.read(r,1);os.waitpid(first,0);os._exit(0)
os.close(r);os.setsid()
if os.fork():os._exit(0)
os.write(w,b'R');os.close(w);time.sleep(0.25)
Path('output/late-marker').write_text('fixture')
'''
        result=self.run_source(source)
        self.assertEqual(result['exit_code'],0,result)
        self.assert_no_late_write(result)

    def test_normal_child_execution_keeps_working(self):
        result=self.run_source('import subprocess,sys;subprocess.run([sys.executable,"-c","print(123)"],check=True)')
        self.assertEqual(result['exit_code'],0,result)
        self.assertEqual(result['stdout'],'123\n',result)

    def test_untrusted_stderr_cannot_disguise_execution_as_not_started(self):
        result=self.run_source('import sys;from pathlib import Path;Path("output/effect.txt").write_text("applied");print("sandbox_apply: Operation not permitted",file=sys.stderr)')
        self.assertEqual(result['decision'],'ALLOW',result)
        self.assertEqual(result['execution_status'],'succeeded',result)
        self.assertEqual(result['effect_status'],'possible',result)
        self.assertEqual((self.work/'output/effect.txt').read_text(),'applied')
        audit=[json.loads(line) for line in (self.base/'state/audit.jsonl').read_text().splitlines()]
        outcome=next(event['result'] for event in audit if event.get('phase')=='result')
        self.assertTrue(outcome['executed'])

    def test_startup_exec_race_retries_identity_before_work(self):
        original=ProcessScope._signal
        raced=[]
        def signal_with_race(scope,identity,kind):
            if kind==signal.SIGCONT and not raced:
                raced.append(identity)
                return False
            return original(scope,identity,kind)
        with patch.object(ProcessScope,'_signal',signal_with_race):
            result=self.run_source('print("native self-test retried")')
        self.assertEqual(result['exit_code'],0,result)
        self.assertEqual(len(raced),1)

    def test_unstable_member_inspection_cannot_report_clean_scope(self):
        scope=ProcessScope(excluded=(self.work,))
        self.addCleanup(scope.close)
        versions=iter(range(10_000))
        with patch.object(scope,'_pids',return_value=[999999]), \
             patch.object(scope,'_info',return_value=SimpleNamespace(status=1)), \
             patch.object(scope,'_checks',return_value=(0,1)), \
             patch.object(scope,'_unique',side_effect=lambda pid:SimpleNamespace(uniqueid=100,version=next(versions))), \
             patch.object(scope,'_signal') as signal_mock, \
             patch.object(scope,'CLEANUP_TIMEOUT',0.02):
            with self.assertRaises(LifecycleUnavailable):scope.terminate()
        self.assertFalse(scope.cleaned)
        signal_mock.assert_not_called()

    def test_marker_files_are_not_inherited_tmpdir_or_command_write_scope(self):
        with patch.dict(os.environ,{'TMPDIR':str(self.work/'output')}):
            scope=ProcessScope(excluded=(self.work,))
        self.addCleanup(scope.close)
        directory=scope.directory.resolve()
        self.assertNotIn(self.work,directory.parents)
        self.assertEqual(directory.parent,Path('/private/tmp'))
        script=self.work/'probe.py'; script.write_text(f'from pathlib import Path;Path({str(scope.allowed)!r}).unlink()')
        argv=[self.python,'-B',str(script)]
        gateway=Gateway(self.work,self.base/'state',{'version':'marker-test',
            'commands':[{'argv':argv,'write_paths':['output']}]})
        # Use this real scope for the command: no inherited TMPDIR permission.
        with patch('guarded_agent.sandbox.ProcessScope',return_value=scope):
            result=gateway.submit(dict(tool='shell',operation='exec',argv=argv))
        self.assertTrue(result['executed'],result)
        self.assertNotEqual(result['exit_code'],0,result)
        self.assertIn('Operation not permitted',result['stderr'])

    def test_marker_scope_overlap_fails_before_work(self):
        with self.assertRaises(LifecycleUnavailable):
            ProcessScope(excluded=('/private/tmp',))

    def test_backend_unavailable_fails_closed_before_work(self):
        argv=[self.python,'-c','print("must not execute")']
        gateway=Gateway(self.work,self.base/'state',{'version':'off','commands':[{'argv':argv}]})
        with patch('guarded_agent.sandbox.ProcessScope',side_effect=LifecycleUnavailable('unavailable')):
            result=gateway.submit(dict(tool='shell',operation='exec',argv=argv))
        self.assertFalse(result['executed'],result)
        self.assertEqual(result['matched_rule'],'SH-SANDBOX',result)
        self.assertEqual(result['stdout'],'')

    def test_cleanup_failure_preserves_started_state_and_blocks_followup(self):
        argv=[self.python,'-c','print("started")']
        gateway=Gateway(self.work,self.base/'state',{'version':'cleanup','commands':[{'argv':argv}]})
        scopes=[]; original=ProcessScope.terminate
        def fail(scope):
            scopes.append(scope)
            raise LifecycleUnavailable('injected inspection failure')
        try:
            with patch.object(ProcessScope,'terminate',fail):
                result=gateway.submit(dict(tool='shell',operation='exec',argv=argv))
            self.assertEqual(result['decision'],'ALLOW',result)
            self.assertTrue(result['executed'],result)
            self.assertEqual(result['execution_error_rule'],'SH-LIFECYCLE',result)
            self.assertEqual(result['execution_status'],'failed',result)
            followup=gateway.submit(dict(tool='filesystem',operation='write',path='later',content='bad'))
            self.assertEqual(followup['matched_rule'],'SH-LIFECYCLE',followup)
            self.assertFalse((self.work/'later').exists())
            audit=[json.loads(line) for line in (self.base/'state/audit.jsonl').read_text().splitlines()]
            outcome=next(event['result'] for event in audit if event.get('phase')=='result')
            self.assertTrue(outcome['executed'])
        finally:
            # Our fixture launched no children; release retained diagnostic files
            # only after real identity-based cleanup, never by widening policy.
            for scope in scopes:
                original(scope);scope.close()

    def test_atomic_signal_rejects_wrong_pidversion_without_killing_own_child(self):
        _,proc,_=_backend()
        child=subprocess.Popen(['/bin/sleep','3'])
        try:
            unique=_UniqueInfo()
            size=proc.proc_pidinfo(child.pid,17,0,ctypes.byref(unique),ctypes.sizeof(unique))
            self.assertEqual(size,ctypes.sizeof(unique))
            token=_AuditToken();token.val[5]=child.pid;token.val[7]=(unique.version+1)&0xffffffff
            self.assertEqual(proc.proc_signal_with_audittoken(ctypes.byref(token),signal.SIGTERM),errno.ESRCH)
            self.assertIsNone(child.poll())
            token.val[7]=unique.version&0xffffffff
            self.assertEqual(proc.proc_signal_with_audittoken(ctypes.byref(token),signal.SIGTERM),0)
            child.wait(timeout=1)
            self.assertEqual(child.returncode,-signal.SIGTERM)
        finally:
            if child.poll() is None:child.kill();child.wait()

    def test_completed_host_does_not_signal_a_reaped_process_group(self):
        output=self.base/'host-output';output.mkdir()
        with patch('guarded_agent.host.os.killpg',side_effect=AssertionError('must not signal a reusable group id')):
            code=capture([self.python,'-c','print("finished")'],'',output,2)
        self.assertEqual(code,0)
        self.assertEqual((output/'events.jsonl').read_text(),'finished\n')

    def test_mcp_marks_applied_edit_failure_as_error(self):
        source=self.work/'source.txt';source.write_text('before\n')
        gateway=Gateway(self.work,self.base/'state');server=Server(gateway);server.ready=True
        original=os.fsync
        def fail_directory(fd):
            import stat
            if stat.S_ISDIR(os.fstat(fd).st_mode):raise OSError('injected directory fsync')
            return original(fd)
        with patch('guarded_agent.filesystem.os.fsync',side_effect=fail_directory):
            reply=server.dispatch({'jsonrpc':'2.0','id':1,'method':'tools/call',
                'params':{'name':'guard_filesystem','arguments':{'operation':'edit','path':'source.txt',
                    'old_text':'before','new_text':'after','expected_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}}})
        outcome=reply['result']['structuredContent']
        self.assertTrue(reply['result']['isError'],reply)
        self.assertEqual(outcome['decision'],'ALLOW',outcome)
        self.assertTrue(outcome['executed'],outcome)
        self.assertEqual(source.read_text(),'after\n')


if __name__=='__main__':unittest.main()
