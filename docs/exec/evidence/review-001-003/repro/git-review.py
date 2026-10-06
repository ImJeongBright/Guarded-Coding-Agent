"""Review-only reproductions using fake content and disposable repositories."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent/'guarded_agent/gateway.py').is_file())
RUN = ROOT/'.guard-runs/review-001-003'
RUN.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))
from guarded_agent.gateway import Gateway
from guarded_agent.git import resolve_executable

git = resolve_executable('/usr/bin/git')
records = {}
with tempfile.TemporaryDirectory(prefix='guard-review-git-') as raw:
    base = Path(raw).resolve()

    def command(work, *args):
        return subprocess.run([git, '-C', str(work), '-c', 'user.name=Fixture',
                               '-c', 'user.email=fixture@example.invalid', *args],
                              check=True, capture_output=True, text=True).stdout

    work = base/'pathspec'; work.mkdir()
    command(work, 'init', '-b', 'feature/review')
    for name in ('one.txt', 'two.txt'):
        (work/name).write_text(name+'\n')
    guard = Gateway(work, base/'pathspec-state')
    request = dict(tool='git', operation='add', paths=['*.txt'])
    result = guard.submit(request)
    staged = command(work, 'ls-files').splitlines()
    assert result['executed'] and result['exit_code'] == 0, result
    assert staged == ['one.txt', 'two.txt'], staged
    records['pathspec_expansion'] = {'request':request, 'decision':result['decision'],
        'executed':result['executed'], 'exit_code':result['exit_code'],
        'literal_target_exists':(work/'*.txt').exists(), 'staged_files':staged}

    work = base/'deleted-sensitive'; work.mkdir()
    command(work, 'init', '-b', 'feature/review')
    dummy = 'not_a_secret_7391'
    (work/'.env').write_text('REVIEW_DUMMY='+dummy+'\n')
    (work/'ordinary.txt').write_text('ordinary\n')
    command(work, 'add', '.env', 'ordinary.txt')
    command(work, 'commit', '-m', 'Fake env fixture')
    command(work, 'rm', '--cached', '.env')
    guard = Gateway(work, base/'sensitive-state')
    direct = guard.submit(dict(tool='filesystem', operation='read', path='.env'))
    request = dict(tool='git', operation='diff', staged=True)
    result = guard.submit(request)
    assert direct['decision'] == 'DENY', direct
    assert result['executed'] and result['exit_code'] == 0, result
    assert dummy in result['stdout'], result
    records['deleted_sensitive_blob'] = {'request':request,
        'direct_read_decision':direct['decision'], 'direct_read_rule':direct['matched_rule'],
        'decision':result['decision'], 'executed':result['executed'],
        'exit_code':result['exit_code'], 'dummy_exposed':True, 'stdout':result['stdout']}

destination = ROOT/'.guard-runs/review-001-003/git-results.json'
destination.write_text(json.dumps(records, indent=2)+'\n')
print(json.dumps(records, indent=2))
