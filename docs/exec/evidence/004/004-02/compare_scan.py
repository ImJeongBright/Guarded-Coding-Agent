"""Compare the exact pre-004-02 traversal pattern with the combined scanner."""
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from guarded_agent.filesystem import Filesystem

def old_link_scan(root):
    for walk_root, directories, files in __import__('os').walk(root, followlinks=False):
        for name in directories + files:
            path = Path(walk_root) / name
            info = path.lstat()
            if path.is_symlink() or (path.is_file() and info.st_nlink != 1):
                raise RuntimeError('Unexpected link fixture')

def old_attribute_scan(root):
    for attr in root.rglob('.gitattributes'):
        raise RuntimeError(f'Unexpected Git attributes: {attr}')

def measure(root, repeats=3):
    fs = Filesystem(root)
    old, combined = [], []
    for _ in range(repeats):
        started = time.perf_counter()
        old_link_scan(root)
        old_link_scan(root)
        old_attribute_scan(root)
        old_attribute_scan(root)
        old_attribute_scan(root)
        old.append(round((time.perf_counter()-started)*1000, 3))

        started = time.perf_counter()
        fs.check_workspace_links(reject_gitattributes=True)
        fs.check_workspace_links(reject_gitattributes=True)
        fs.check_workspace_links(reject_gitattributes=True)
        combined.append(round((time.perf_counter()-started)*1000, 3))
    return {'old_five_passes_ms':old,'old_median_ms':round(statistics.median(old),3),
            'combined_three_passes_ms':combined,'combined_median_ms':round(statistics.median(combined),3),
            'reduction_percent':round((1-statistics.median(combined)/statistics.median(old))*100,2)}

results = {}
for name in ('M1-3000-10000','M2-10000-25000'):
    work = ROOT/'.guard-runs'/'scale-probe-02'/name/'workspace'
    results[name] = measure(work)
(BASE/'scan-comparison.json').write_text(json.dumps({
    'fixture_only':True,
    'repeats':3,
    'semantics':'legacy = 2 old link walks + 3 Path.rglob(.gitattributes); combined = 3 integrity walks',
    'results':results,
},indent=2)+'\n')
print(json.dumps(results,indent=2),flush=True)
