from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from guarded_agent.gateway import Gateway
from guarded_agent.mcp import Server

class SandboxEdgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve(); self.work=self.base/'work'; self.work.mkdir()

    def run_source(self, source, timeout=20):
        argv=[str(Path(sys.executable).resolve()),'-c',source]
        g=Gateway(self.work,self.base/'state',{'version':'edges','commands':[{'argv':argv,'timeout':timeout,'write_paths':['link']}]})
        result=g.submit({'tool':'shell','operation':'exec','argv':argv})
        self.assertTrue(result['executed'],result)
        return result

    def test_runtime_symlink_escape_denied(self):
        outside=self.base/'private'; outside.write_text('private-value')
        result=self.run_source(f'from pathlib import Path; Path("link").symlink_to({str(outside)!r}); print(Path("link").read_text())')
        self.assertNotEqual(result['exit_code'],0,result)
        self.assertNotIn('private-value',result['stdout'])

    def test_runtime_hardlink_escape_denied(self):
        outside=self.base/'private'; outside.write_text('private-value')
        result=self.run_source(f'import os; os.link({str(outside)!r}, "link")')
        self.assertNotEqual(result['exit_code'],0,result)
        self.assertFalse((self.work/'link').exists())

    def test_system_volume_alias_outside_read_denied(self):
        outside=self.base/'private'; outside.write_text('fake-volume-private-value')
        alias=Path('/System/Volumes/Data'+str(outside))
        self.assertTrue(alias.samefile(outside))
        result=self.run_source(f'from pathlib import Path; print(Path({str(alias)!r}).read_text())')
        self.assertNotEqual(result['exit_code'],0,result)
        self.assertNotIn('fake-volume-private-value',result['stdout'])

    def test_shell_git_metadata_denied(self):
        (self.work/'.git').mkdir(); (self.work/'.git/config').write_text('safe')
        result=self.run_source('from pathlib import Path; Path(".git/config").write_text("bad")')
        self.assertNotEqual(result['exit_code'],0,result)
        self.assertEqual((self.work/'.git/config').read_text(),'safe')

    def test_clean_environment_has_no_inherited_secret(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ,{'GUARD_FAKE_SECRET':'private-value','BASH_ENV':'/outside'}):
            result=self.run_source('import os; print(os.environ.get("GUARD_FAKE_SECRET")); print(os.environ.get("BASH_ENV"))')
        self.assertEqual(result['exit_code'],0,result)
        self.assertNotIn('private-value',result['stdout'])
        self.assertEqual(result['stdout'].strip(),'None\nNone')

    def test_selected_python_runtime_is_read_only_and_keeps_secret_boundary(self):
        from unittest.mock import patch
        runtime=self.base/'controller-python'; runtime.mkdir()
        (runtime/'library').write_text('trusted runtime fixture')
        (runtime/'.env').write_text('private runtime fixture')
        neighbor=self.base/'unrelated'; neighbor.write_text('outside fixture')
        source=f'''from pathlib import Path
print(Path({str(runtime/'library')!r}).read_text())
for name, operation in [({str(runtime/'new-file')!r},'write'),
                         ({str(runtime/'.env')!r},'read'), ({str(neighbor)!r},'read')]:
 try:
  p=Path(name)
  p.write_text('bad') if operation=='write' else p.read_text()
 except PermissionError: print('denied')
 else: raise AssertionError('runtime scope expanded')
'''
        with patch('guarded_agent.sandbox.sys.base_prefix', str(runtime)):
            result=self.run_source(source)
        self.assertEqual(result['exit_code'],0,result)
        self.assertEqual(result['stdout'],'trusted runtime fixture\ndenied\ndenied\ndenied\n')
        self.assertFalse((runtime/'new-file').exists())

    def test_output_is_bounded(self):
        result=self.run_source('import sys; sys.stdout.write("x" * 100000)')
        self.assertEqual(result['exit_code'],0,result)
        self.assertEqual(len(result['stdout']),64000)
        self.assertTrue(result['output_truncated'])

    def test_child_file_size_limit_stops_at_32_mib(self):
        (self.work/'build').mkdir()
        argv=[sys.executable,'-B','-c',
              'from pathlib import Path; Path("build/oversized.bin").write_bytes(b"x"*(33*1024*1024))']
        g=Gateway(self.work,self.base/'file-size',{'version':'size',
            'commands':[{'argv':argv,'write_paths':['build']}]})
        result=g.submit({'tool':'shell','operation':'exec','argv':argv})
        self.assertTrue(result['executed'],result)
        self.assertNotEqual(result['exit_code'],0,result)
        self.assertEqual((self.work/'build/oversized.bin').stat().st_size,32*1024*1024)
        self.assertIn('File too large',result['stderr'])

    def test_compiler_with_explicit_sdk(self):
        cc=subprocess.check_output(['/usr/bin/xcrun','--find','cc'],text=True).strip()
        sdk=subprocess.check_output(['/usr/bin/xcrun','--show-sdk-path'],text=True).strip()
        (self.work/'main.c').write_text('#include <stdio.h>\nint main(void) { puts("ok"); return 0; }\n')
        argv=[cc,'-isysroot',sdk,'-Wall','-Wextra','-Werror','main.c','-o','app']
        g=Gateway(self.work,self.base/'compiler',{'version':'c','commands':[{'argv':argv,'write_paths':['app']}]})
        result=g.submit({'tool':'shell','operation':'exec','argv':argv})
        self.assertEqual(result['exit_code'],0,result)
        self.assertTrue((self.work/'app').exists())

    def test_mcp_malformed_and_preinitialize_no_execution(self):
        g=Gateway(self.work,self.base/'server')
        server=Server(g)
        probe=server.dispatch({'jsonrpc':'2.0','id':0,'method':'server/discover','params':{}})
        self.assertEqual(probe['error']['code'],-32601)
        result=server.dispatch({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'guard_filesystem','arguments':{'operation':'write','path':'a','content':'bad'}}})
        self.assertIn('error',result)
        self.assertFalse((self.work/'a').exists())
        self.assertIn('error',server.dispatch([]))

if __name__=='__main__':
    unittest.main()
