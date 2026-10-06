import json
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch
from guarded_agent.host import command, configuration, preflight, toml_value


class HostProfileTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.base=Path(tmp.name); self.work=self.base/'work'; self.work.mkdir()
        self.state=self.base/'state'; self.state.mkdir()
        (self.state/'policy.json').write_text(json.dumps({'version':'test','commands':[]}))

    def test_host_boundary_and_serialization(self):
        config=configuration(self.work,self.state)
        self.assertEqual(config['sandbox_mode'],'read-only')
        self.assertEqual(config['approval_policy'],'never')
        self.assertFalse(config['features']['shell_tool'])
        self.assertFalse(config['features']['view_image'])
        self.assertEqual(set(config['mcp_servers']),{'guard'})
        self.assertTrue(config['mcp_servers']['guard']['required'])
        self.assertEqual(tomllib.loads('profile = '+toml_value(config))['profile'],config)
        with patch('guarded_agent.host.shutil.which',return_value='/bin/codex'):
            args=command(self.work,self.state)
        self.assertIn('--ignore-user-config',args)
        self.assertNotIn('--dangerously-bypass-hook-trust',args)
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox',args)

    @patch('guarded_agent.host.codex_version', return_value='codex-cli 0.160.0')
    def test_preflight_and_agent_owned_state_rejected(self, version):
        self.assertEqual(len(preflight(self.work,self.state)['hook_sha256']),64)
        with self.assertRaises(ValueError):
            configuration(self.work,self.work)
        (self.state/'policy.json').write_text('invalid')
        with self.assertRaises(ValueError):
            preflight(self.work,self.state)

    def test_unreviewed_project_config_rejected(self):
        (self.work/'.codex').mkdir()
        (self.work/'.codex/config.toml').write_text('sandbox_mode="workspace-write"')
        with self.assertRaisesRegex(ValueError,'separate host review'):
            preflight(self.work,self.state)

    @patch('guarded_agent.host.codex_version', return_value='codex-cli unreviewed')
    def test_unreviewed_host_version_rejected(self, version):
        with self.assertRaisesRegex(ValueError,'different version'):
            preflight(self.work,self.state)


if __name__=='__main__':
    unittest.main()
