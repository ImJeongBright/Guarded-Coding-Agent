from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from guarded_agent.gateway import Gateway

class CommandWriteScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve(); self.work=self.base/'work'; self.work.mkdir()
        (self.work/'source.c').write_text('safe')

    def execute(self,source,write_paths):
        argv=[str(Path(sys.executable).resolve()),'-c',source]
        g=Gateway(self.work,self.base/'state',{'version':'scope','commands':[{'argv':argv,'write_paths':write_paths}]})
        result=g.submit({'tool':'shell','operation':'exec','argv':argv})
        self.assertTrue(result['executed'],result)
        return result

    def test_no_write_scope_is_read_only(self):
        result=self.execute('from pathlib import Path; Path("source.c").write_text("bad")',[])
        self.assertNotEqual(result['exit_code'],0,result)
        self.assertEqual((self.work/'source.c').read_text(),'safe')

    def test_unicode_and_space_write_scope(self):
        result=self.execute('from pathlib import Path; Path("빌드 결과.txt").write_text("ok")',['빌드 결과.txt'])
        self.assertEqual(result['exit_code'],0,result)
        self.assertEqual((self.work/'빌드 결과.txt').read_text(),'ok')

    def test_build_scope_allows_artifact_but_denies_source_delete(self):
        (self.work/'build').mkdir()
        result=self.execute('from pathlib import Path; Path("build/a.o").write_text("object")', ['build'])
        self.assertEqual(result['exit_code'],0,result)
        self.assertEqual((self.work/'build/a.o').read_text(),'object')
        result=self.execute('from pathlib import Path; Path("source.c").unlink()', ['build'])
        self.assertNotEqual(result['exit_code'],0,result)
        self.assertTrue((self.work/'source.c').exists())

    def test_outside_or_entire_workspace_write_profile_invalid(self):
        argv=['/usr/bin/true']
        for path in ['.','../outside','.git','.env']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                Gateway(self.work,self.base/'invalid',{'version':'scope','commands':[{'argv':argv,'write_paths':[path]}]})

    def test_write_scope_swap_after_validation_cannot_expand_sandbox(self):
        outside=self.base/'outside'; outside.mkdir()
        argv=[str(Path(sys.executable).resolve()),'-c','from pathlib import Path; Path("build/escaped").write_text("bad")']
        g=Gateway(self.work,self.base/'state',{'version':'scope','commands':[{'argv':argv,'write_paths':['build']}]})
        original=g.shell._execute
        def swap(action):
            (self.work/'build').symlink_to(outside,target_is_directory=True)
            return original(action)
        with patch.object(g.shell,'_execute',side_effect=swap):
            result=g.submit({'tool':'shell','operation':'exec','argv':argv})
        self.assertFalse((outside/'escaped').exists(),result)
        self.assertEqual(result['decision'],'DENY',result)
        self.assertFalse(result['executed'],result)

if __name__=='__main__':
    unittest.main()
