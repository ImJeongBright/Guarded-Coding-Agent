"""Combined workspace integrity and Git-attribute scan regressions."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from guarded_agent.domain import Action
from guarded_agent.filesystem import Blocked
from guarded_agent.gateway import Gateway


class WorkspaceScanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='guard-workspace-scan-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.work = self.base/'work'
        self.work.mkdir()
        self.command = [str(Path(sys.executable).resolve()), '-c', 'print("workspace scan")']
        policy = {'version':'004-02', 'commands':[{'argv':self.command}], 'git_remotes':{}}
        self.guard = Gateway(self.work, self.base/'state', policy)
        subprocess.run([self.guard.git.executable, 'init', '-b', 'feature/scan', str(self.work)],
                       check=True, capture_output=True)

    def test_git_attributes_are_rejected_in_combined_scan_but_shell_allows_them(self):
        nested = self.work/'module'/'nested'
        nested.mkdir(parents=True)
        (nested/'.gitattributes').write_text('* text=auto\n')
        with patch.object(self.guard.git, '_execute', side_effect=AssertionError(
                'Git started despite workspace attributes')) as execute:
            git_result = self.guard.submit({'tool':'git', 'operation':'status'})
        self.assertEqual(git_result['matched_rule'], 'GT-CONFIG', git_result)
        self.assertFalse(git_result['executed'], git_result)
        execute.assert_not_called()

        shell_result = self.guard.submit({'tool':'shell', 'operation':'exec', 'argv':self.command})
        self.assertEqual(shell_result['exit_code'], 0, shell_result)
        self.assertTrue(shell_result['executed'], shell_result)

    def test_attribute_added_after_git_config_check_is_caught_before_executor(self):
        action = Action('git', 'status', {'args':['status', '--short']})

        def add_attributes():
            nested = self.work/'late'/'module'
            nested.mkdir(parents=True)
            (nested/'.gitattributes').write_text('* filter=unexpected\n')

        with patch.object(self.guard.git, '_config_check', side_effect=add_attributes), \
             patch('guarded_agent.git.sandbox.run') as run:
            with self.assertRaises(Blocked) as error:
                self.guard.git._execute(action)
        self.assertEqual(error.exception.rule, 'GT-CONFIG')
        run.assert_not_called()

    def test_hardlink_added_after_git_config_check_is_caught_before_executor(self):
        outside = self.base/'outside.txt'
        outside.write_text('outside data\n')
        action = Action('git', 'status', {'args':['status', '--short']})

        def add_hardlink():
            os.link(outside, self.work/'late-hardlink.txt')

        with patch.object(self.guard.git, '_config_check', side_effect=add_hardlink), \
             patch('guarded_agent.git.sandbox.run') as run:
            with self.assertRaises(Blocked) as error:
                self.guard.git._execute(action)
        self.assertEqual(error.exception.rule, 'FS-LINK')
        run.assert_not_called()

    def test_unreadable_or_disappearing_scan_entry_fails_closed(self):
        ordinary = self.work/'ordinary.txt'
        ordinary.write_text('ordinary\n')
        original_lstat = Path.lstat

        def vanishing(path, *args, **kwargs):
            if path == ordinary:
                raise FileNotFoundError(str(path))
            return original_lstat(path, *args, **kwargs)

        with patch.object(Path, 'lstat', vanishing):
            with self.assertRaises(Blocked) as error:
                self.guard.fs.check_workspace_links(reject_gitattributes=True)
        self.assertEqual(error.exception.rule, 'FS-LINK')


if __name__ == '__main__':
    unittest.main()
