"""Read-only review of product code; all mutations are temporary fixtures."""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from unittest.mock import patch

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent/'guarded_agent/gateway.py').is_file())
RUN = ROOT/'.guard-runs/review-001-003'
RUN.mkdir(parents=True, exist_ok=True)
sys.path.insert(0,str(ROOT))
from guarded_agent.gateway import Gateway

results = {}
with tempfile.TemporaryDirectory(prefix='guard-review-fs-') as directory:
    base = Path(directory)
    work = base/'work'
    work.mkdir()
    g = Gateway(work,base/'state')
    source = work/'source.txt'
    source.write_text('before\n')
    actual_fsync = os.fsync

    def fail_directory_sync(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError('injected directory fsync failure after replace')
        return actual_fsync(fd)

    with patch('guarded_agent.filesystem.os.fsync',side_effect=fail_directory_sync):
        outcome = g.submit(dict(tool='filesystem',operation='edit',path='source.txt',
            old_text='before',new_text='after',
            expected_sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
    event = json.loads((base/'state/audit.jsonl').read_text().splitlines()[-1])
    assert source.read_text() == 'after\n'
    assert outcome['decision'] == 'DENY' and outcome['executed'] is False, outcome
    assert event['result']['executed'] is False, event
    results['edit_post_mutation_failure'] = {
        'outcome':outcome,'actual_content':source.read_text(),
        'audit_result':event['result'],
    }

    entries = work/'many'
    entries.mkdir()
    for i in range(5001):
        (entries/f'{i:05}.txt').write_text('needle\n')
    outcome = g.submit(dict(tool='filesystem',operation='search',path='many',query='needle'))
    assert outcome['matches'] == [] and outcome['scanned_bytes'] == 0 and outcome['truncated'], outcome
    results['search_large_directory'] = {'actual_matching_files':5001,'outcome':outcome}
    outcome = g.submit(dict(tool='filesystem',operation='list',path='many'))
    assert len(outcome['stdout'].splitlines()) == 2000 and 'truncated' not in outcome, outcome
    results['list_large_directory'] = {
        'actual_files':5001,'reported_files':len(outcome['stdout'].splitlines()),
        'has_truncated_field':'truncated' in outcome,
        'decision':outcome['decision'],'exit_code':outcome['exit_code'],
    }

    (work/'large.txt').write_text('needle\n'+'x'*1_000_000)
    outcome = g.submit(dict(tool='filesystem',operation='search',path='large.txt',query='needle'))
    assert outcome['matches'] == [] and outcome['truncated'] is False, outcome
    results['search_oversized_file'] = {'outcome':outcome,'actual_match':True}

target = RUN/'filesystem-results.json'
target.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(results,ensure_ascii=False,indent=2))
