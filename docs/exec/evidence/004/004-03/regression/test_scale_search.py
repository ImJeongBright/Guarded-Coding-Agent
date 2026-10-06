"""Search-budget regressions for explicit generated-directory exclusions."""
import os
from pathlib import Path
import tempfile
import unittest

from guarded_agent.gateway import Gateway


class SearchExclusionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='guard-search-scale-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.work = self.base/'work'
        self.work.mkdir()
        self.guard = Gateway(self.work, self.base/'state')

    def search(self, path='.', **args):
        return self.guard.submit({'tool':'filesystem','operation':'search',
                                  'path':path,'query':'TARGET_MARKER',**args})

    def test_generated_tree_exhaustion_is_avoided_by_exact_exclusion(self):
        build = self.work/'build'
        build.mkdir()
        for index in range(5_005):
            (build/f'generated_{index:05}.txt').write_text('no source match\n')
        module = self.work/'src'/'module_a'
        module.mkdir(parents=True)
        (module/'target.c').write_text('/* TARGET_MARKER */\n')

        broad = self.search(glob='*.c')
        self.assertTrue(broad['incomplete'], broad)
        self.assertIn('entry_limit', broad['truncation_reasons'])
        self.assertEqual(broad['matches'], [])

        scoped = self.search(glob='*.c', exclude_dirs=['build'])
        self.assertEqual(scoped['matches'], [{'path':'src/module_a/target.c',
                                               'line':1,'text':'/* TARGET_MARKER */'}], scoped)
        self.assertFalse(scoped['incomplete'], scoped)
        self.assertEqual(scoped['excluded_dirs'], ['build'])

    def test_exclusion_is_relative_to_search_path_and_skips_nested_contents(self):
        module = self.work/'src'/'module_a'
        (module/'generated').mkdir(parents=True)
        (module/'generated/secret.txt').write_text('TARGET_MARKER should not be returned\n')
        (module/'main.c').write_text('TARGET_MARKER in source\n')

        result = self.search('src', exclude_dirs=['module_a/generated'])
        self.assertEqual([match['path'] for match in result['matches']], ['src/module_a/main.c'])
        self.assertEqual(result['excluded_dirs'], ['src/module_a/generated'])
        self.assertFalse(result['incomplete'], result)

    def test_exclusions_reject_escape_files_symlinks_and_self(self):
        source = self.work/'source.c'
        source.write_text('TARGET_MARKER\n')
        outside = self.base/'outside'
        outside.mkdir()
        (self.work/'linked').symlink_to(outside, target_is_directory=True)
        requests = [
            {'exclude_dirs':['../outside']},
            {'exclude_dirs':[str(outside)]},
            {'exclude_dirs':['.']},
            {'exclude_dirs':['source.c']},
            {'exclude_dirs':['linked']},
            {'exclude_dirs':[f'generated_{i}' for i in range(33)]},
        ]
        for args in requests:
            with self.subTest(args=args):
                result = self.search(**args)
                self.assertEqual(result['decision'], 'DENY', result)
                self.assertFalse(result['executed'], result)

    def test_excluded_hardlink_content_is_never_read_or_audited(self):
        outside = self.base/'outside.txt'
        outside.write_text('TARGET_MARKER private excluded value\n')
        generated = self.work/'generated'
        generated.mkdir()
        os.link(outside, generated/'linked.txt')

        result = self.search(exclude_dirs=['generated'])
        self.assertEqual(result['matches'], [])
        self.assertNotIn('private excluded value', str(result))
        audit = (self.base/'state'/'audit.jsonl').read_text()
        self.assertNotIn('private excluded value', audit)


if __name__ == '__main__':
    unittest.main()
