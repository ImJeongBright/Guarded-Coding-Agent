"""Operator-only final fault fixtures. No model, network, or real repository data.

The controller-kill case deliberately demonstrates a limitation: SIGKILL skips
finally. A trusted test harness retains the native scope identity before launch
and cleans it up. This is NOT a product supervisor or automatic recovery API.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from guarded_agent.gateway import Gateway
from guarded_agent.mcp import Server
from guarded_agent.process_lifecycle import ProcessScope, _backend


def audit_probe(base):
    base = Path(base); base.mkdir()
    work = base/'work'; work.mkdir()
    guard = Gateway(work, base/'state')
    server = Server(guard); server.ready = True
    original = guard.fs._execute

    def fail_result_storage(action):
        outcome = original(action)
        # Actual open failure after a durable decision and an applied FS write.
        guard.audit.path.rename(base/'decision-audit.jsonl')
        guard.audit.path.mkdir()
        return outcome

    with patch.object(guard.fs, '_execute', side_effect=fail_result_storage):
        reply = server.dispatch({'jsonrpc':'2.0', 'id':1, 'method':'tools/call',
            'params':{'name':'guard_filesystem', 'arguments':{
                'operation':'write', 'path':'effect.txt', 'content':'applied fixture'}}})
    outcome = reply['result']['structuredContent']
    # Restoring storage alone must not hide a missing execution record.
    guard.audit.path.rmdir()
    (base/'decision-audit.jsonl').rename(guard.audit.path)
    followup = guard.submit(dict(tool='filesystem', operation='write', path='later.txt', content='later'))
    fresh = Gateway(work, base/'state')
    recovered = fresh.submit(dict(tool='filesystem', operation='read', path='effect.txt'))
    return {'injection':'audit path replaced by directory after executor write',
        'effect_bytes':(work/'effect.txt').read_text(), 'outcome':outcome,
        'mcp_is_error':reply['result']['isError'], 'followup':followup,
        'followup_effect_exists':(work/'later.txt').exists(), 'fresh_read':recovered,
        'audit_phases':[json.loads(line)['phase'] for line in guard.audit.path.read_text().splitlines()]}


def wait_for(path, controller, seconds=5):
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        if path.exists():
            return
        if controller.poll() is not None:
            raise RuntimeError('Controller ended before fixture handshake: '+str(controller.returncode))
        time.sleep(0.01)
    raise TimeoutError('Fixture handshake did not arrive.')


def controller_probe(base):
    base = Path(base).resolve(); base.mkdir()
    work = base/'work'; work.mkdir(); (work/'output').mkdir()
    outside = base/'outside-marker'
    # A bounded child waits for operator release after a proven ready state.
    child = f'''import os,time
from pathlib import Path
Path('output/ready').write_text(str(os.getpid()))
deadline=time.monotonic()+8
while not Path('output/release').exists() and time.monotonic()<deadline: time.sleep(0.01)
if Path('output/release').exists():
 Path('output/late-marker').write_text('after controller kill')
 try: Path({str(outside)!r}).write_text('must remain denied')
 except PermissionError: Path('output/outside-denied').write_text('denied')
 time.sleep(2)
'''
    argv = [str(Path(sys.executable).resolve()), '-B', '-c', child]
    (base/'policy.json').write_text(json.dumps({'version':'005-controller-fixture',
        'commands':[{'argv':argv, 'write_paths':['output'], 'timeout':10}]}))
    controller_source = f'''import json,sys
from pathlib import Path
sys.path.insert(0,{str(ROOT)!r})
from guarded_agent import sandbox
from guarded_agent.gateway import Gateway
from guarded_agent.process_lifecycle import ProcessScope
class CapturedScope(ProcessScope):
 def __init__(self,**kwargs):
  super().__init__(**kwargs)
  Path({str(base/'scope-capture.json')!r}).write_text(json.dumps({{
   'directory':str(self.directory),'allowed':str(self.allowed),'denied':str(self.denied)}}))
sandbox.ProcessScope=CapturedScope
g=Gateway({str(work)!r},{str(base/'state')!r},policy_path={str(base/'policy.json')!r})
print(json.dumps(g.submit({{'tool':'shell','operation':'exec','argv':{argv!r}}})),flush=True)
'''
    (base/'controller.py').write_text(controller_source)
    scope = None
    with (base/'controller.stdout').open('w') as output, (base/'controller.stderr').open('w') as errors:
        controller = subprocess.Popen([sys.executable, '-B', str(base/'controller.py')],
            stdout=output, stderr=errors, start_new_session=True)
        try:
            wait_for(base/'scope-capture.json', controller)
            saved = json.loads((base/'scope-capture.json').read_text())
            # Rehydrate only this trusted fixture's scope for operator cleanup.
            scope = ProcessScope.__new__(ProcessScope)
            scope.sandbox, scope.proc, scope.quiet = _backend()
            scope.directory, scope.allowed, scope.denied = (Path(saved[key]) for key in ('directory','allowed','denied'))
            scope.started, scope.cleaned = True, False
            wait_for(work/'output/ready', controller)
            before = scope.members()
            if not before: raise AssertionError('No live contained command before kill.')
            controller.kill(); controller.wait(timeout=2)
            after = scope.members()
            (work/'output/release').write_text('operator fixture release')
            deadline = time.monotonic()+1
            while not (work/'output/outside-denied').exists() and time.monotonic()<deadline:
                time.sleep(0.01)
            facts = {'injection':'SIGKILL of controller after command ready handshake',
                'controller_exit':controller.returncode, 'members_before_kill':len(before),
                'members_after_kill':len(after), 'late_allowed_write':(work/'output/late-marker').exists(),
                'outside_write':outside.exists(), 'outside_denial_observed':(work/'output/outside-denied').exists(),
                'controller_result_bytes':(base/'controller.stdout').stat().st_size,
                'audit_phases':[json.loads(line)['phase'] for line in (base/'state/audit.jsonl').read_text().splitlines()],
                'automatic_scope_record':(scope.directory/'scope.json').exists()}
        finally:
            if controller.poll() is None: controller.kill(); controller.wait(timeout=2)
            if scope is not None:
                terminated = scope.terminate()
                empty = not scope.members()
                scope.close()
    facts.update(operator_terminated_processes=terminated, operator_scope_empty=empty)
    return facts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='New operator fixture directory')
    args = parser.parse_args()
    base = Path(args.output).resolve(); base.mkdir(parents=True, exist_ok=False)
    result = {'audit':audit_probe(base/'audit'), 'controller':controller_probe(base/'controller')}
    (base/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
