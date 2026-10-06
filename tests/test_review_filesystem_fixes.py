"""Regression coverage for review R002, R006 and R007."""
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from guarded_agent.domain import MAX_CONTENT, MAX_OUTPUT
from guarded_agent.execution import ExecutionFailure
from guarded_agent.gateway import Gateway


class FilesystemReviewFixTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.work = self.base/'work'; self.work.mkdir()
        self.file = self.work/'a.txt'; self.file.write_text('before\n')
        self.g = Gateway(self.work,self.base/'state')

    def fs(self, operation, path='a.txt', **data):
        return self.g.submit({'tool':'filesystem','operation':operation,'path':path,**data})

    def edit(self):
        return self.fs('edit',old_text='before',new_text='after',
                       expected_sha256=hashlib.sha256(self.file.read_bytes()).hexdigest())

    def assert_audit_outcome(self, result):
        events = [json.loads(line) for line in (self.base/'state/audit.jsonl').read_text().splitlines()]
        audit_result = events[-1]['result']
        self.assertEqual(events[-1]['phase'],'result')
        for field in ('decision','executed','execution_status','effect_status','execution_stage'):
            self.assertEqual(audit_result.get(field),result.get(field),field)

    def assert_started_failure(self, result, status, stage):
        self.assertEqual(result['decision'],'ALLOW',result)
        self.assertTrue(result['executed'],result)
        self.assertEqual(result['execution_status'],'failed')
        self.assertEqual(result['effect_status'],status)
        self.assertEqual(result['execution_stage'],stage)
        self.assertEqual(result['execution_error_rule'],'EXEC-ERROR')
        self.assert_audit_outcome(result)

    def test_edit_replace_then_directory_fsync_failure_reports_applied(self):
        real_fsync = os.fsync
        def fail_directory(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError('directory fsync failed')
            return real_fsync(fd)
        with patch('guarded_agent.filesystem.os.fsync',side_effect=fail_directory):
            result = self.edit()
        self.assertEqual(self.file.read_text(),'after\n')
        self.assert_started_failure(result,'applied','edit_directory_fsync')
        self.assertEqual(list(self.work.glob('.guard-edit-*')),[])

    def test_write_data_fsync_failure_reports_partial_and_actual_content(self):
        real_fsync = os.fsync
        identity = self.file.stat().st_ino
        def fail_target(fd):
            if os.fstat(fd).st_ino==identity:
                raise OSError('data fsync failed')
            return real_fsync(fd)
        with patch('guarded_agent.filesystem.os.fsync',side_effect=fail_target):
            result = self.fs('write',content='changed\n')
        self.assertEqual(self.file.read_text(),'changed\n')
        self.assert_started_failure(result,'partial','write_data_fsync')

    def test_write_truncated_then_data_setup_failure_reports_partial(self):
        real_dup = os.dup
        identity = self.file.stat().st_ino
        def fail_target_dup(fd):
            if os.fstat(fd).st_ino==identity:
                raise OSError('data descriptor failed')
            return real_dup(fd)
        with patch('guarded_agent.filesystem.os.dup',side_effect=fail_target_dup):
            result = self.fs('write',content='changed\n')
        self.assertEqual(self.file.read_text(),'')
        self.assert_started_failure(result,'partial','write_data')

    def test_existing_write_truncate_failure_reports_not_started(self):
        with patch('guarded_agent.filesystem.os.ftruncate',side_effect=OSError('pre-mutation failure')):
            result = self.fs('write',content='changed\n')
        self.assertEqual(self.file.read_text(),'before\n')
        self.assertEqual(result['decision'],'DENY')
        self.assertFalse(result['executed'])
        self.assertEqual(result['effect_status'],'none')
        self.assertEqual(result['execution_status'],'not_started')
        self.assert_audit_outcome(result)

    def test_parent_creation_followed_by_failure_reports_partial(self):
        real_mkdir = os.mkdir
        def fail_second_parent(path,*args,**kwargs):
            if path=='second':
                raise OSError('parent creation failed')
            return real_mkdir(path,*args,**kwargs)
        with patch('guarded_agent.filesystem.os.mkdir',side_effect=fail_second_parent):
            result = self.fs('write','first/second/file.txt',content='changed')
        self.assertTrue((self.work/'first').is_dir())
        self.assertFalse((self.work/'first/second').exists())
        self.assert_started_failure(result,'partial','write_parent_create')

    def test_new_file_creation_then_descriptor_failure_reports_partial(self):
        real_fstat = os.fstat
        target = self.work/'new.txt'
        def fail_created_file(fd):
            info = real_fstat(fd)
            if target.exists() and info.st_ino==target.stat().st_ino:
                raise OSError('created descriptor check failed')
            return info
        with patch('guarded_agent.filesystem.os.fstat',side_effect=fail_created_file):
            result = self.fs('write','new.txt',content='changed')
        self.assertTrue(target.exists())
        self.assertEqual(target.read_text(),'')
        self.assert_started_failure(result,'partial','write_descriptor_check')

    def test_edit_failed_replace_and_cleanup_reports_retained_temporary_effect(self):
        real_unlink = os.unlink
        def fail_temporary(path,*args,**kwargs):
            if str(path).startswith('.guard-edit-'):
                raise OSError('temporary cleanup failed')
            return real_unlink(path,*args,**kwargs)
        with patch('guarded_agent.filesystem.os.replace',side_effect=OSError('replace failed')), \
                patch('guarded_agent.filesystem.os.unlink',side_effect=fail_temporary):
            result = self.edit()
        self.assertEqual(self.file.read_text(),'before\n')
        self.assertEqual(len(list(self.work.glob('.guard-edit-*'))),1)
        self.assert_started_failure(result,'partial','edit_temporary_cleanup')

    def test_successful_write_and_read_have_truthful_effect_metadata(self):
        write = self.fs('write',content='changed\n')
        self.assertEqual(write['effect_status'],'applied')
        self.assertEqual(write['execution_status'],'succeeded')
        read = self.fs('read')
        self.assertEqual(read['effect_status'],'none')
        self.assertEqual(read['execution_status'],'succeeded')

    def test_executor_failure_preserves_policy_and_audit(self):
        failure = ExecutionFailure('started process failed',executed=True,
                                   effect_status='possible',stage='process_wait',exit_code=124)
        with patch.object(self.g.fs,'_execute',side_effect=failure):
            result = self.fs('read')
        self.assertEqual(result['decision'],'ALLOW')
        self.assertEqual(result['matched_rule'],'FS-LOCAL')
        self.assertTrue(result['executed'])
        self.assertEqual(result['exit_code'],124)
        self.assertEqual(result['effect_status'],'possible')
        self.assert_audit_outcome(result)

    def test_nonzero_exit_is_execution_failure_without_policy_denial(self):
        with patch.object(self.g.fs,'_execute',return_value={'exit_code':1,'stdout':'','stderr':'failed'}):
            result = self.fs('read')
        self.assertEqual(result['decision'],'ALLOW')
        self.assertEqual(result['execution_status'],'failed')
        self.assertTrue(result['executed'])
        self.assert_audit_outcome(result)

    def test_search_entry_limit_processes_already_collected_files(self):
        for number in range(5001):
            (self.work/f'entry-{number:04}.txt').write_text('needle\n')
        result = self.fs('search','.',query='needle',glob='entry-*.txt')
        self.assertEqual(result['decision'],'ALLOW')
        self.assertEqual(len(result['matches']),200)
        self.assertGreater(result['scanned_bytes'],0)
        self.assertEqual(result['scanned_entries'],5000)
        self.assertIn('entry_limit',result['truncation_reasons'])
        self.assertTrue(result['incomplete'])
        self.assertLessEqual(result['scanned_bytes'],8_000_000)

    def test_direct_oversized_search_is_explicit_size_denial(self):
        self.file.write_text('needle'+'x'*MAX_CONTENT)
        result = self.fs('search',query='needle')
        self.assertEqual(result['decision'],'DENY')
        self.assertEqual(result['matched_rule'],'FS-SIZE')
        self.assertFalse(result['executed'])

    def test_recursive_oversized_search_reports_incomplete(self):
        (self.work/'large.txt').write_text('needle'+'x'*MAX_CONTENT)
        result = self.fs('search','.',query='needle')
        self.assertEqual(result['matches'],[])
        self.assertTrue(result['truncated'])
        self.assertTrue(result['incomplete'])
        self.assertEqual(result['truncation_reasons'],['file_size_limit'])
        self.assertEqual(result['skipped_oversized_files'],1)

    def test_file_growth_cannot_exceed_remaining_search_byte_budget(self):
        for number in range(7):
            (self.work/f'budget-{number:02}.txt').write_text('x'*MAX_CONTENT)
        (self.work/'budget-07.txt').write_text('x'*900_000)
        growing = self.work/'budget-08.txt'; growing.write_text('small')
        identity = growing.stat().st_ino
        real_read = self.g.fs.read_bytes
        def grow_before_read(fd,maximum=MAX_CONTENT):
            if os.fstat(fd).st_ino==identity:
                growing.write_text('x'*200_000)
            return real_read(fd,maximum=maximum)
        with patch.object(self.g.fs,'read_bytes',side_effect=grow_before_read):
            result = self.fs('search','.',query='needle')
        self.assertEqual(result['decision'],'ALLOW')
        self.assertEqual(result['matches'],[])
        self.assertLessEqual(result['scanned_bytes'],8_000_000)
        self.assertEqual(result['truncation_reasons'],['byte_limit'])
        self.assertTrue(result['incomplete'])

    def test_list_reports_entry_result_limits(self):
        for number in range(5001):
            (self.work/f'entry-{number:04}.txt').touch()
        result = self.fs('list','.')
        self.assertEqual(result['returned_entries'],2000)
        self.assertEqual(result['scanned_entries'],5000)
        self.assertTrue(result['truncated'])
        self.assertTrue(result['incomplete'])
        self.assertEqual(result['truncation_reasons'],['entry_limit','result_limit'])
        self.assertLessEqual(len(result['stdout'].encode()),MAX_OUTPUT)

    def test_list_output_bound_counts_utf8_bytes(self):
        for number in range(400):
            (self.work/(f'{number:04}-'+'가'*60)).touch()
        result = self.fs('list','.')
        self.assertIn('output_limit',result['truncation_reasons'])
        self.assertLess(result['returned_entries'],401)
        self.assertLessEqual(len(result['stdout'].encode()),MAX_OUTPUT)

    def test_complete_list_reports_no_truncation(self):
        result = self.fs('list','.')
        self.assertEqual(result['stdout'],'a.txt')
        self.assertFalse(result['truncated'])
        self.assertFalse(result['incomplete'])
        self.assertEqual(result['truncation_reasons'],[])


if __name__=='__main__':
    unittest.main()
