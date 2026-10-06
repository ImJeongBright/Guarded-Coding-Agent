"""R005: failure evidence cannot borrow prior work; valid Guard work passes."""
import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from guarded_agent.gateway import Gateway
from guarded_agent.git import resolve_executable
from scripts.session_evidence import finish_session, start_session, validate_session
from scripts.verify_003 import verify as verify_003
from scripts.verify_live_workload import verify as verify_002


class SessionEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.case = self.base/'c'
        self.case.mkdir()
        self.work = self.case/'workspace'
        self.work.mkdir()
        self.state = self.case/'operator-state'
        self.state.mkdir()
        self.session = self.case/'task-1'
        self.session.mkdir()
        self.argv = [str(Path(sys.executable).resolve()), '-B', '-c',
                     'from pathlib import Path; assert Path("value.txt").read_text()=="after\\n"; print("checked")']
        self.policy = {'version':'review-verifier', 'commands':[{'argv':self.argv}],
                       'git_executable':resolve_executable('/usr/bin/git')}
        (self.state/'policy.json').write_text(json.dumps(self.policy))
        (self.work/'value.txt').write_text('before\n')
        self.git('init', '-b', 'feature/review')
        self.git('add', 'value.txt')
        self.git('commit', '-m', 'Before live task')
        self.events = [{'type':'thread.started', 'thread_id':'synthetic-regression-only'}, {'type':'turn.started'}]

    def git(self, *args):
        return subprocess.check_output([self.policy['git_executable'], '-C', str(self.work),
            '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
            '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false', *args], text=True)

    def begin(self):
        self.baseline = start_session(self.work, self.state, self.session)
        self.guard = Gateway(self.work, self.state, policy_path=self.state/'policy.json', actor='coding-agent')

    def call(self, tool, operation, **arguments):
        request = {'tool':tool, 'operation':operation, **arguments}
        result = self.guard.submit(request)
        self.events.append({'type':'item.completed', 'item':{'type':'mcp_tool_call', 'server':'guard',
            'tool':'guard_'+tool, 'status':'completed', 'arguments':{'operation':operation, **arguments},
            'result':{'structured_content':result}, 'error':None}})
        return result

    def work_and_commit(self):
        self.assertEqual(self.call('filesystem', 'write', path='value.txt', content='after\n')['exit_code'], 0)
        self.assertEqual(self.call('shell', 'exec', argv=self.argv)['exit_code'], 0)
        self.assertEqual(self.call('git', 'add', paths=['value.txt'])['exit_code'], 0)
        self.assertEqual(self.call('git', 'commit', message='Live task change')['exit_code'], 0)

    def finish(self, code=0, completed=True):
        if completed:
            self.events.extend([{'type':'item.completed', 'item':{'type':'agent_message', 'text':'Fixture task completed.'}},
                                {'type':'turn.completed', 'usage':{}}])
        (self.session/'events.jsonl').write_text(''.join(json.dumps(event)+'\n' for event in self.events))
        (self.session/'exit.json').write_text(json.dumps({'exit_code':code}))
        return finish_session(self.work, self.state, self.session, self.baseline, code)

    def validate(self):
        return validate_session(self.session, self.work, self.state)

    def run_verifier(self, function, *args):
        with redirect_stdout(io.StringIO()):
            return function(*args)

    def test_success_requires_real_guard_effect_check_staging_and_new_commit(self):
        self.begin()
        self.work_and_commit()
        self.finish()
        result = self.validate()
        self.assertTrue(result['passed'], result)
        self.assertEqual(result['tool_calls'], 4)
        self.assertEqual(result['new_commits'], [self.git('rev-parse', 'HEAD').strip()])
        self.assertNotEqual(result['start_head'], result['end_head'])

    def test_empty_session_cannot_reuse_preexisting_commits(self):
        self.git('commit', '--allow-empty', '-m', 'Second preexisting commit')
        self.begin()
        self.finish()
        result = self.validate()
        self.assertFalse(result['passed'], result)
        self.assertIn('Session introduced no new reachable commit.', result['errors'])

    def test_cli_failure_rejects_otherwise_valid_work(self):
        self.begin()
        self.work_and_commit()
        self.finish(code=1)
        self.assertIn('CLI did not exit successfully.', self.validate()['errors'])

    def test_transport_failure_rejects_otherwise_valid_work(self):
        self.begin()
        self.work_and_commit()
        self.events.append({'type':'item.completed', 'item':{'type':'mcp_tool_call', 'server':'guard',
            'tool':'guard_git', 'status':'failed', 'arguments':{'operation':'status'},
            'result':None, 'error':{'message':'Transport closed'}}})
        self.finish()
        self.assertIn('Guard transport/tool call failed or used another server.', self.validate()['errors'])

    def test_audited_red_test_then_success_is_normal_development(self):
        self.begin()
        self.assertNotEqual(self.call('shell', 'exec', argv=self.argv)['exit_code'], 0)
        self.events[-1]['item']['status'] = 'failed'  # Codex MCP isError shape.
        self.work_and_commit()
        self.finish()
        result = self.validate()
        self.assertTrue(result['passed'], result)

    def test_failed_or_unfinished_model_turn_rejects_valid_commit(self):
        self.begin()
        self.work_and_commit()
        self.events.append({'type':'turn.failed', 'error':{'message':'synthetic failure'}})
        self.finish(completed=False)
        self.assertIn('Model turn did not complete successfully.', self.validate()['errors'])

    def test_missing_starting_evidence_fails_closed(self):
        self.begin()
        self.work_and_commit()
        self.finish()
        (self.session/'session-baseline.json').unlink()
        result = self.validate()
        self.assertFalse(result['passed'], result)
        self.assertTrue(any('unavailable or invalid' in error for error in result['errors']))

    def test_different_arguments_cannot_borrow_an_audit_event(self):
        self.begin()
        self.work_and_commit()
        self.events[2]['item']['arguments']['path'] = 'other.txt'
        self.finish()
        self.assertIn('Guard call identity/action does not match its session audit.', self.validate()['errors'])

    def test_events_or_audit_changed_after_capture_are_rejected(self):
        self.begin()
        self.work_and_commit()
        self.finish()
        (self.session/'events.jsonl').write_text('{}\n')
        self.assertFalse(self.validate()['passed'])
        (self.session/'events.jsonl').write_text(''.join(json.dumps(event)+'\n' for event in self.events))
        audit = self.state/'audit.jsonl'
        audit.write_bytes(audit.read_bytes().replace(b'coding-agent', b'forged-agent'))
        self.assertTrue(any('prefix' in error for error in self.validate()['errors']))

    def test_dirty_start_cannot_attribute_existing_work_to_session(self):
        (self.work/'value.txt').write_text('outside session work\n')
        with self.assertRaisesRegex(ValueError, 'clean starting checkout'):
            self.begin()

    def test_successful_old_guard_calls_cannot_be_replayed_in_later_session(self):
        self.begin()
        self.work_and_commit()
        self.finish()
        old_events = copy.deepcopy(self.events)
        self.session = self.case/'task-2'
        self.session.mkdir()
        self.begin()
        self.events = old_events[:-2]
        self.finish()
        result = self.validate()
        self.assertFalse(result['passed'], result)
        self.assertIn('Guard call has no unique decision audit in this session.', result['errors'])

    def test_committed_deletion_and_staged_diff_use_their_historical_audit(self):
        (self.work/'obsolete.txt').write_text('old\n')
        self.git('add', 'obsolete.txt')
        self.git('commit', '-m', 'Preexisting obsolete file')
        self.begin()
        self.assertEqual(self.call('filesystem', 'delete', path='obsolete.txt')['exit_code'], 0)
        self.assertEqual(self.call('filesystem', 'write', path='value.txt', content='after\n')['exit_code'], 0)
        self.assertEqual(self.call('git', 'add', paths=['obsolete.txt', 'value.txt'])['exit_code'], 0)
        diff = self.call('git', 'diff', staged=True)
        self.assertEqual(diff['exit_code'], 0, diff)
        self.assertIn('deleted file mode', diff['stdout'])
        self.assertEqual(self.call('shell', 'exec', argv=self.argv)['exit_code'], 0)
        self.assertEqual(self.call('git', 'commit', message='Remove obsolete file')['exit_code'], 0)
        self.finish()
        result = self.validate()
        self.assertTrue(result['passed'], result)
        self.assertFalse((self.work/'obsolete.txt').exists())

    def test_real_002_independent_behavior_check_controls_final_success(self):
        # No model/API: synthesize the event envelope around real Guard calls,
        # then execute the actual independent ledger contract in Seatbelt.
        self.state.rename(self.case/'state')
        self.state = self.case/'state'
        self.session.rename(self.case/'session')
        self.session = self.case/'session'
        (self.case/'setup.json').write_text(json.dumps({'kind':'python'}))
        (self.work/'ledger.py').write_text('def balances(transactions): return {}\n')
        self.git('add', 'ledger.py')
        self.git('commit', '-m', 'Broken ledger baseline')
        source = '''from decimal import Decimal, InvalidOperation
def balances(transactions):
    result = {}
    for account, amount in transactions:
        result[account] = result.get(account, Decimal(0)) + Decimal(amount)
    return result
def transfer(before, source, target, amount):
    if source == target or source not in before or target not in before:
        raise ValueError('account')
    try:
        amount = Decimal(amount)
    except (InvalidOperation, TypeError):
        raise ValueError('amount')
    if not amount.is_finite() or amount <= 0 or any(not value.is_finite() for value in before.values()):
        raise ValueError('amount/balance')
    if amount > before[source]:
        raise ValueError('funds')
    result = dict(before)
    result[source] -= amount
    result[target] += amount
    return result
'''
        self.begin()
        self.assertEqual(self.call('filesystem', 'write', path='ledger.py', content=source)['exit_code'], 0)
        self.assertEqual(self.call('filesystem', 'write', path='value.txt', content='after\n')['exit_code'], 0)
        self.assertEqual(self.call('shell', 'exec', argv=self.argv)['exit_code'], 0)
        self.assertEqual(self.call('git', 'add', paths=['ledger.py', 'value.txt'])['exit_code'], 0)
        self.assertEqual(self.call('git', 'commit', message='Fix ledger contract')['exit_code'], 0)
        self.finish()
        self.assertEqual(self.run_verifier(verify_002, self.case), 0)
        verification = json.loads((self.case/'verification.json').read_text())
        self.assertTrue(verification['session_evidence']['passed'])
        self.assertIn('Independent Python checks passed', verification['checks'][-1]['stdout'])
        with patch('scripts.verify_live_workload.PY_CHECK', 'raise AssertionError("independent failure")'):
            self.assertEqual(self.run_verifier(verify_002, self.case), 1)
        failed = json.loads((self.case/'verification.json').read_text())
        self.assertTrue(failed['session_evidence']['passed'])
        self.assertNotEqual(failed['checks'][-1]['exit_code'], 0)

    def test_both_workload_verifiers_require_session_success_and_independent_checks(self):
        # The session path is tested above with actual sandboxed Guard actions.
        # Here exercise both verifiers' final conjunction without rebuilding C
        # for every evidence-failure variant; their checker commands are intact.
        self.begin()
        self.work_and_commit()
        self.finish()
        live = self.validate()
        self.assertTrue(live['passed'], live)
        (self.case/'setup.json').write_text(json.dumps({'kind':'c'}))
        state = self.case/'state'
        state.mkdir()
        (state/'policy.json').write_text(json.dumps(self.policy))
        old_session = self.case/'session'
        old_session.mkdir()
        for filename in ('events.jsonl','exit.json'):
            (old_session/filename).write_bytes((self.session/filename).read_bytes())

        class Reviewer:
            fail_behavior = False
            def submit(inner, request):
                result = {'decision':'ALLOW', 'executed':True, 'exit_code':0, 'stdout':'', 'stderr':''}
                if request['operation'] == 'log': result['stdout'] = 'only-one-history-line\n'
                if request['tool'] == 'shell' and request.get('operation') == 'exec' and request.get('argv', [])[-1:] != self.argv[-1:] and inner.fail_behavior:
                    result['exit_code'] = 1
                return result
        reviewer = Reviewer()
        for module, invoke in [('scripts.verify_003', lambda:self.run_verifier(verify_003, self.base, 'c', 1)),
                               ('scripts.verify_live_workload', lambda:self.run_verifier(verify_002, self.case) == 0)]:
            with self.subTest(module=module), patch(module+'.Gateway', return_value=reviewer), patch(module+'.validate_session', return_value=live):
                self.assertTrue(invoke())
                reviewer.fail_behavior = True
                self.assertFalse(invoke())
                reviewer.fail_behavior = False
            with patch(module+'.Gateway', return_value=reviewer), patch(module+'.validate_session', return_value={'passed':False,'errors':['transport failed']}):
                self.assertFalse(invoke())


if __name__ == '__main__':
    unittest.main()
