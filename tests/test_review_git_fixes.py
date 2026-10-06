"""Regression coverage for R001 historical blobs and R004 literal file scope."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from guarded_agent.gateway import Gateway


class ReviewGitFixTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='guard-git-fix-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.work = self.base/'work'
        self.work.mkdir()
        self.guard = Gateway(self.work, self.base/'state')
        self.git = self.guard.git.executable
        self.command('init', '-b', 'feature/review')

    def command(self, *args):
        return subprocess.run([self.git, '-C', str(self.work),
                               '-c', 'user.name=Fixture',
                               '-c', 'user.email=fixture@example.invalid', *args],
                              check=True, capture_output=True, text=True).stdout

    def request(self, operation, **args):
        return self.guard.submit(dict(tool='git', operation=operation, **args))

    def commit_file(self, name, content):
        (self.work/name).write_text(content)
        self.command('--literal-pathspecs', 'add', '--', name)
        self.command('commit', '-m', 'Fixture commit')

    def assert_sensitive_diff_denied(self, **args):
        with patch.object(self.guard.git, '_execute', side_effect=AssertionError(
                'Sensitive metadata reached the patch executor')) as execute:
            result = self.request('diff', staged=True, **args)
        self.assertEqual(result['matched_rule'], 'FS-SENSITIVE', result)
        self.assertFalse(result['executed'], result)
        self.assertNotIn('review_fixture_value', json.dumps(result))
        self.assertNotIn('review_fixture_value', (self.base/'state/audit.jsonl').read_text())
        execute.assert_not_called()

    def test_staged_sensitive_deletion_denied_before_blob_read(self):
        self.commit_file('.env', 'DUMMY=review_fixture_value\n')
        self.command('rm', '--cached', '--', '.env')
        self.assert_sensitive_diff_denied()

    def test_staged_sensitive_rename_denied_before_blob_read(self):
        self.commit_file('.env', 'DUMMY=review_fixture_value\n')
        self.command('mv', '--', '.env', 'ordinary.txt')
        self.assert_sensitive_diff_denied()

    def test_new_name_filter_cannot_hide_sensitive_rename_source(self):
        self.commit_file('.env', 'DUMMY=review_fixture_value\n')
        self.command('mv', '--', '.env', 'ordinary.txt')
        self.assert_sensitive_diff_denied(paths=['ordinary.txt'])

    def test_unborn_staged_diff_and_later_unstaged_diff_still_work(self):
        (self.work/'ordinary.txt').write_text('first\n')
        self.assertEqual(self.request('add', paths=['ordinary.txt'])['exit_code'], 0)
        staged = self.request('diff', staged=True, paths=['ordinary.txt'])
        self.assertEqual(staged['exit_code'], 0, staged)
        self.assertIn('+first', staged['stdout'])
        self.command('commit', '-m', 'Initial ordinary file')
        (self.work/'ordinary.txt').write_text('second\n')
        unstaged = self.request('diff', paths=['ordinary.txt'])
        self.assertEqual(unstaged['exit_code'], 0, unstaged)
        self.assertIn('-first', unstaged['stdout'])
        self.assertIn('+second', unstaged['stdout'])

    def test_normal_deleted_file_can_be_staged_and_reviewed(self):
        self.commit_file('ordinary.txt', 'original\n')
        (self.work/'ordinary.txt').unlink()
        staged = self.request('add', paths=['ordinary.txt'])
        self.assertEqual(staged['exit_code'], 0, staged)
        review = self.request('diff', staged=True, paths=['ordinary.txt'])
        self.assertEqual(review['exit_code'], 0, review)
        self.assertIn('-original', review['stdout'])

    def test_wildcard_without_literal_target_never_stages_other_files(self):
        for name in ('one.txt', 'two.txt'):
            (self.work/name).write_text(name+'\n')
        result = self.request('add', paths=['*.txt'])
        self.assertEqual(result['matched_rule'], 'GT-PATHS', result)
        self.assertFalse(result['executed'], result)
        self.assertEqual(self.command('ls-files'), '')

    def test_literal_wildcard_and_magic_filenames_stage_only_the_named_file(self):
        for name in ('one.txt', '*.txt', ':(glob)*.txt'):
            (self.work/name).write_text(name+'\n')
        for name in ('*.txt', ':(glob)*.txt'):
            result = self.request('add', paths=[name])
            self.assertEqual(result['exit_code'], 0, result)
        self.assertEqual(self.command('ls-files', '-z').split('\0')[:-1], ['*.txt', ':(glob)*.txt'])
        review = self.request('diff', staged=True, paths=['*.txt'])
        self.assertEqual(review['exit_code'], 0, review)
        self.assertIn('+*.txt', review['stdout'])
        self.assertNotIn(':(glob)', review['stdout'])
        self.assertNotIn('one.txt', review['stdout'])

    def test_directory_recursion_denied_for_add_and_diff(self):
        (self.work/'dir').mkdir()
        (self.work/'dir/a.txt').write_text('a\n')
        for operation in ('add', 'diff'):
            result = self.request(operation, paths=['dir'])
            self.assertEqual(result['matched_rule'], 'GT-PATHS', result)
            self.assertFalse(result['executed'], result)
        self.assertEqual(self.command('ls-files'), '')

    def test_deleted_directory_is_not_an_explicit_tracked_file(self):
        (self.work/'dir').mkdir()
        self.commit_file('dir/a.txt', 'original\n')
        (self.work/'dir/a.txt').unlink()
        (self.work/'dir').rmdir()
        result = self.request('add', paths=['dir'])
        self.assertEqual(result['matched_rule'], 'GT-PATHS', result)
        self.assertFalse(result['executed'], result)
        self.assertEqual(self.command('diff', '--cached', '--name-only'), '')

    def test_whitespace_and_unicode_filenames_are_validated_without_strip(self):
        name = ' 공백 파일.txt '
        (self.work/name).write_text('ordinary\n')
        result = self.request('add', paths=[name])
        self.assertEqual(result['exit_code'], 0, result)
        review = self.request('diff', staged=True, paths=[name])
        self.assertEqual(review['exit_code'], 0, review)
        self.assertIn('+ordinary', review['stdout'])

    def test_truncated_diff_metadata_denies_before_executor(self):
        def incomplete(argv, *args, **kwargs):
            is_diff = 'diff' in argv
            return dict(exit_code=0, stdout='ordinary.txt\0' if is_diff else '',
                        stderr='', output_truncated=is_diff)
        with patch('guarded_agent.git.sandbox.run', side_effect=incomplete), patch.object(
                self.guard.git, '_execute') as execute:
            result = self.request('diff', staged=True)
        self.assertEqual(result['matched_rule'], 'GT-STATE', result)
        self.assertFalse(result['executed'], result)
        execute.assert_not_called()

    def test_malformed_diff_metadata_denies_before_executor(self):
        for raw in ('ordinary.txt', 'ordinary.txt\0\0', 'bad\ufffdname\0', '../ordinary.txt\0'):
            with self.subTest(raw=raw):
                def malformed(argv, *args, **kwargs):
                    return dict(exit_code=0, stdout=raw if 'diff' in argv else '',
                                stderr='', output_truncated=False)
                with patch('guarded_agent.git.sandbox.run', side_effect=malformed), patch.object(
                        self.guard.git, '_execute') as execute:
                    result = self.request('diff', staged=True)
                self.assertEqual(result['decision'], 'DENY', result)
                self.assertFalse(result['executed'], result)
                execute.assert_not_called()


if __name__=='__main__':
    unittest.main()
