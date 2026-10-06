"""Final audit gap and controller loss contracts, using disposable real effects."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from guarded_agent.cli import main
from guarded_agent.gateway import Gateway
from scripts.final_failure_probe import audit_probe, controller_probe


class FinalFailureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='guard-final-failures-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()

    def test_result_audit_failure_preserves_effect_and_requires_operator_restart(self):
        facts = audit_probe(self.base/'audit')
        outcome = facts['outcome']
        self.assertEqual(facts['effect_bytes'], 'applied fixture')
        self.assertEqual((outcome['decision'], outcome['executed'], outcome['effect_status']),
                         ('ALLOW', True, 'applied'))
        self.assertEqual(outcome['execution_status'], 'succeeded')
        self.assertIn('audit_error', outcome)
        self.assertTrue(facts['mcp_is_error'], facts)
        self.assertEqual(facts['followup']['matched_rule'], 'AU-ERROR', facts)
        self.assertFalse(facts['followup']['executed'], facts)
        self.assertFalse(facts['followup_effect_exists'], facts)
        self.assertEqual(facts['fresh_read']['stdout'], 'applied fixture')
        self.assertEqual(facts['audit_phases'], ['decision', 'decision', 'decision', 'result'])

    def test_cli_returns_failure_when_effect_succeeds_but_result_audit_is_missing(self):
        work = self.base/'work'; work.mkdir()
        guard = Gateway(work, self.base/'state')
        record = guard.audit.record
        def fail_result(event):
            if event['phase'] == 'result': raise OSError('injected result storage outage')
            return record(event)
        output = io.StringIO()
        request = dict(tool='filesystem', operation='write', path='effect.txt', content='applied')
        argv = ['guard', 'exec', '--workspace', str(work), '--state', str(guard.state)]
        with patch('sys.argv', argv), patch('sys.stdin', io.StringIO(json.dumps(request))), \
             patch('guarded_agent.cli.Gateway', return_value=guard), \
             patch.object(guard.audit, 'record', side_effect=fail_result), redirect_stdout(output):
            code = main()
        self.assertEqual(code, 1)
        self.assertEqual((work/'effect.txt').read_text(), 'applied')
        outcome = json.loads(output.getvalue())
        self.assertTrue(outcome['executed'])
        self.assertIn('audit_error', outcome)

    def test_controller_sigkill_retains_scope_but_needs_operator_cleanup(self):
        facts = controller_probe(self.base/'controller')
        self.assertEqual(facts['controller_exit'], -9)
        self.assertGreaterEqual(facts['members_before_kill'], 1)
        self.assertGreaterEqual(facts['members_after_kill'], 1)
        self.assertTrue(facts['late_allowed_write'], facts)
        self.assertFalse(facts['outside_write'], facts)
        self.assertTrue(facts['outside_denial_observed'], facts)
        self.assertEqual(facts['controller_result_bytes'], 0)
        self.assertEqual(facts['audit_phases'], ['decision'])
        self.assertFalse(facts['automatic_scope_record'])
        self.assertGreaterEqual(facts['operator_terminated_processes'], 1)
        self.assertTrue(facts['operator_scope_empty'])


if __name__ == '__main__':
    unittest.main()
