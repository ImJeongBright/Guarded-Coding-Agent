from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

BINARY=(Path(__file__).resolve().parent.parent/'build/minidb')

class DatabaseTests(unittest.TestCase):
    def setUp(self):
        # All child test files stay in the sandbox workspace.
        test_root=Path(__file__).resolve().parent.parent/'build/test-data'
        test_root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='db-test-',dir=test_root)
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)

    def run_db(self, commands):
        return subprocess.run([str(BINARY)],input=commands,cwd=self.path,text=True,capture_output=True,timeout=3)

    def database_snapshot(self):
        # Exclude access time: loading the database is allowed to read it.
        return {
            entry.name: (entry.read_bytes(), entry.stat().st_ino,
                         entry.stat().st_size, entry.stat().st_mtime_ns,
                         entry.stat().st_ctime_ns, entry.stat().st_mode)
            for entry in self.path.iterdir()
        }

    def assert_help_is_read_only(self):
        expected=('Commands:\ninsert <uint32 id> <name>\nselect\n'
                  'count\nfind <uint32 id>\n.help\n.exit\n')
        before=self.database_snapshot()
        for commands in ['.help\n', '.help\n.exit\n', '.help\n.help\n.exit\n']:
            with self.subTest(commands=commands):
                result=self.run_db(commands)
                self.assertEqual(result.returncode,0)
                self.assertEqual(result.stdout,expected*commands.count('.help'))
                self.assertEqual(result.stderr,'')
                self.assertEqual(self.database_snapshot(),before)

    def test_help_empty_is_read_only(self):
        self.assert_help_is_read_only()
        self.assertEqual(self.database_snapshot(),{})

    def test_help_persisted_empty_is_read_only(self):
        (self.path/'data.db').write_bytes(b'GDB1'+struct.pack('<I',0))
        self.assert_help_is_read_only()

    def test_help_existing_persisted_database_is_read_only(self):
        result=self.run_db('insert 0 zero\ninsert 4294967295 max\n.exit\n')
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stdout,'Executed.\nExecuted.\n')
        self.assertEqual(result.stderr,'')
        self.assert_help_is_read_only()

    def test_insert_select_and_restart(self):
        self.assertIn('Executed.',self.run_db('insert 1 alice\n.exit\n').stdout)
        result=self.run_db('select\n.exit\n')
        self.assertEqual(result.returncode,0)
        self.assertIn('(1, alice)',result.stdout)

    def test_zero_and_uint32_max(self):
        result=self.run_db('insert 0 zero\ninsert 4294967295 max\nselect\n.exit\n')
        self.assertIn('(0, zero)',result.stdout)
        self.assertIn('(4294967295, max)',result.stdout)

    def test_duplicate_preserves_row(self):
        result=self.run_db('insert 3 first\ninsert 3 second\nselect\n.exit\n')
        self.assertIn('duplicate',result.stdout)
        self.assertNotIn('(3, second)',result.stdout)
        self.assertIn('(3, first)',result.stdout)

    def test_count_empty_is_read_only(self):
        result=self.run_db('count\ncount\n.exit\n')
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stdout,'Count: 0\nCount: 0\n')
        self.assertFalse((self.path/'data.db').exists())

    def test_count_zero_duplicates_and_restart(self):
        result=self.run_db('count\ninsert 0 zero\ncount\ninsert 0 other\ncount\ninsert 4294967295 max\ncount\n.exit\n')
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stdout.splitlines(),[
            'Count: 0','Executed.','Count: 1','Error: duplicate id.',
            'Count: 1','Executed.','Count: 2'])
        expected=(b'GDB1'+struct.pack('<I',2)+struct.pack('<I32s',0,b'zero')
                  +struct.pack('<I32s',4294967295,b'max'))
        self.assertEqual((self.path/'data.db').read_bytes(),expected)
        result=self.run_db('count\ninsert 0 other\ncount\nselect\n.exit\n')
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stdout.splitlines(),[
            'Count: 2','Error: duplicate id.','Count: 2',
            '(0, zero)','(4294967295, max)','Executed.'])
        self.assertEqual((self.path/'data.db').read_bytes(),expected)

    def test_count_existing_binary_format(self):
        data=b'GDB1'+struct.pack('<I',1)+struct.pack('<I32s',0,b'legacy')
        (self.path/'data.db').write_bytes(data)
        result=self.run_db('count\nselect\ncount extra\n.exit\n')
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stdout.splitlines(),[
            'Count: 1','(0, legacy)','Executed.','Error: invalid statement.'])
        self.assertEqual((self.path/'data.db').read_bytes(),data)

    def test_find_empty_is_read_only(self):
        result=self.run_db('find 0\nfind 4294967295\n.exit\n')
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stdout,'Not found.\nNot found.\n')
        self.assertEqual(self.database_snapshot(),{})
        result=self.run_db('find 1\n')
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stdout,'Not found.\n')
        self.assertEqual(result.stderr,'')
        self.assertEqual(self.database_snapshot(),{})

    def test_find_persisted_empty_is_read_only(self):
        (self.path/'data.db').write_bytes(b'GDB1'+struct.pack('<I',0))
        before=self.database_snapshot()
        for commands in ['find 0\nfind 4294967295\n.exit\n','find 1\n']:
            with self.subTest(commands=commands):
                result=self.run_db(commands)
                self.assertEqual(result.returncode,0)
                self.assertEqual(result.stdout,'Not found.\n'*commands.count('find'))
                self.assertEqual(result.stderr,'')
                self.assertEqual(self.database_snapshot(),before)

    def test_find_duplicate_inserts_preserve_original_after_restart(self):
        result=self.run_db('insert 0 zero\ninsert 4294967295 max\n'
                           'insert 0 other\ninsert 4294967295 other\n'
                           'find 0\nfind 4294967295\n.exit\n')
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stdout.splitlines(),[
            'Executed.','Executed.','Error: duplicate id.',
            'Error: duplicate id.','(0, zero)','(4294967295, max)'])
        before=self.database_snapshot()
        result=self.run_db('insert 0 other\ninsert 4294967295 other\n'
                           'find 4294967295\nfind 0\nfind 1\n.exit\n')
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stdout.splitlines(),[
            'Error: duplicate id.','Error: duplicate id.',
            '(4294967295, max)','(0, zero)','Not found.'])
        self.assertEqual(result.stderr,'')
        self.assertEqual(self.database_snapshot(),before)

    def test_find_boundaries_and_restart(self):
        result=self.run_db('insert 0 zero\ninsert 42 alice\ninsert 4294967295 max\nfind 42\nfind 0\nfind 4294967295\nfind 1\n.exit\n')
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stdout.splitlines(),[
            'Executed.','Executed.','Executed.','(42, alice)',
            '(0, zero)','(4294967295, max)','Not found.'])
        expected=(b'GDB1'+struct.pack('<I',3)+struct.pack('<I32s',0,b'zero')
                  +struct.pack('<I32s',42,b'alice')
                  +struct.pack('<I32s',4294967295,b'max'))
        self.assertEqual((self.path/'data.db').read_bytes(),expected)
        before=self.database_snapshot()
        result=self.run_db('find 4294967295\nfind 42\nfind 0\nfind 1\nfind 43\n.exit\n')
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stdout,'(4294967295, max)\n(42, alice)\n(0, zero)\nNot found.\nNot found.\n')
        self.assertEqual(result.stderr,'')
        self.assertEqual(self.database_snapshot(),before)
        self.assertEqual((self.path/'data.db').read_bytes(),expected)

    def test_find_invalid_arguments_preserve_data(self):
        commands=['find','find -1','find +1','find 4294967296',
                  'find 9999999999999999999999999999999999999999',
                  'find 1x','find 1.0','find abc','find 0 extra',
                  'find 0 extra more','find 0x1','find 1e0','find 1_0',
                  'find0','Find 0','find --1']
        invalid='\n'.join(commands)+'\n'
        result=self.run_db(invalid+'.exit\n')
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stdout,'Error: invalid statement.\n'*len(commands))
        self.assertFalse((self.path/'data.db').exists())
        self.assertEqual(self.database_snapshot(),{})
        data=b'GDB1'+struct.pack('<I',1)+struct.pack('<I32s',0,b'legacy')
        (self.path/'data.db').write_bytes(data)
        before=self.database_snapshot()
        result=self.run_db(invalid+'find 0\ncount\nselect\n.exit\n')
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stdout,'Error: invalid statement.\n'*len(commands)
                         +'(0, legacy)\nCount: 1\n(0, legacy)\nExecuted.\n')
        self.assertEqual((self.path/'data.db').read_bytes(),data)
        self.assertEqual(result.stderr,'')
        self.assertEqual(self.database_snapshot(),before)

    def test_invalid_input_never_creates_database(self):
        result=self.run_db('insert -1 bad\ninsert 4294967296 bad\ninsert 1 '+'a'*32+'\ninsert 2 ok extra\ninsert 1x bad\n.exit\n')
        self.assertEqual(result.stdout.count('invalid statement'),5)
        self.assertFalse((self.path/'data.db').exists())

    def test_capacity_and_eof(self):
        result=self.run_db(''.join(f'insert {i} row{i}\n' for i in range(101)))
        self.assertEqual(result.stdout.count('Executed.'),100)
        self.assertIn('table full',result.stdout)
        self.assertEqual(result.returncode,0)

    def test_corrupt_and_truncated_data_rejected(self):
        for data in [b'bad',b'GDB1'+struct.pack('<I',101),b'GDB1'+struct.pack('<I',1)+b'broken',b'GDB1'+struct.pack('<I',0)+b'extra']:
            (self.path/'data.db').write_bytes(data)
            result=self.run_db('select\n')
            self.assertEqual(result.returncode,1)
            self.assertIn('invalid database',result.stderr)

    def test_overlong_input_recovery(self):
        result=self.run_db('x'*5000+'\ninsert 1 ok\nselect\n.exit\n')
        self.assertIn('input too long',result.stdout)
        self.assertIn('(1, ok)',result.stdout)

    def test_persistence_failure_is_reported_and_rolled_back(self):
        (self.path/'data.db.tmp').mkdir()
        result=self.run_db('insert 1 nope\nselect\ncount\n.exit\n')
        self.assertIn('persistence failed',result.stdout)
        self.assertNotIn('(1, nope)',result.stdout)
        self.assertIn('Count: 0\n',result.stdout)
        self.assertFalse((self.path/'data.db').exists())

if __name__=='__main__':
    unittest.main(verbosity=2)
