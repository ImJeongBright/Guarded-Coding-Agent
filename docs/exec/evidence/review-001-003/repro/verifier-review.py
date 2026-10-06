"""Show that an empty synthetic live session can pass the 003 verifier."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent/'guarded_agent/gateway.py').is_file())
RUN = ROOT/'.guard-runs/review-001-003'
RUN.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))
from guarded_agent.git import resolve_executable
from scripts.verify_003 import verify
from scripts.verify_live_workload import verify as verify_002

git = resolve_executable('/usr/bin/git')
with tempfile.TemporaryDirectory(prefix='guard-review-verifier-') as raw:
    base = Path(raw).resolve(); case = base/'c'; case.mkdir()
    work = case/'workspace'
    source = ROOT/'docs/exec/evidence/003/c/final-source'
    shutil.copytree(source, work, ignore=shutil.ignore_patterns('.git', 'build', '__pycache__'))
    (work/'build').mkdir()
    (work/'.gitignore').write_text('build/\n*.db\n__pycache__/\n')

    def command(*args):
        return subprocess.run([git, '-C', str(work), '-c', 'user.name=Fixture',
                               '-c', 'user.email=fixture@example.invalid', *args],
                              check=True, capture_output=True, text=True).stdout

    command('init', '-b', 'feature/review')
    command('add', '.')
    command('commit', '-m', 'Correct source prepared before session')
    command('commit', '--allow-empty', '-m', 'Preexisting history before session')
    head_before = command('rev-parse', 'HEAD').strip()
    policy = json.loads((ROOT/'docs/exec/evidence/003/c/policy.json').read_text())
    policy['commands'] = [p for p in policy['commands'] if p['id'] != 'c-db']
    for profile in policy['commands']:
        if profile['id'] == 'c-tests': profile['argv'][0] = str(Path(sys.executable).resolve())
    (case/'operator-state').mkdir()
    (case/'operator-state/policy.json').write_text(json.dumps(policy))
    session = case/'task-1'; session.mkdir()
    # Deliberately synthetic: mirrors the CLI-zero/failed-tool-session failure class.
    (session/'events.jsonl').write_text(json.dumps({'type':'item.completed',
        'item':{'type':'agent_message', 'text':'Synthetic failure: no Guard tools were used.'}})+'\n')
    (session/'exit.json').write_text(json.dumps({'exit_code':0}))
    passed = verify(base, 'c', 1)
    result = json.loads((case/'verification-1.json').read_text())
    head_after = command('rev-parse', 'HEAD').strip()
    assert passed and result['tool_calls'] == 0 and head_before == head_after, result
    record = {'synthetic_failure_fixture':True, 'verifier_passed':passed,
        'tool_calls':result['tool_calls'], 'new_commit_after_session':head_before != head_after,
        'model_final':result['model_final'],
        'checks':[{'label':c['label'], 'executed':c['executed'], 'exit_code':c['exit_code']} for c in result['checks']],
        'git_clean':not result['git_status']['stdout'].strip()}
    # The 002 verifier uses the same project/check pattern and does not read CLI exit.
    (case/'setup.json').write_text(json.dumps({'kind':'c'}))
    (case/'state').mkdir()
    (case/'state/policy.json').write_text(json.dumps(policy))
    old_session = case/'session'; old_session.mkdir()
    (old_session/'events.jsonl').write_text((session/'events.jsonl').read_text())
    (old_session/'exit.json').write_text(json.dumps({'exit_code':1}))
    old_passed = verify_002(case) == 0
    old_result = json.loads((case/'verification.json').read_text())
    assert old_passed and old_result['model_tool_calls'] == 0, old_result
    record['002'] = {'verifier_passed':old_passed, 'tool_calls':old_result['model_tool_calls'],
        'synthetic_cli_exit_code':1, 'new_commit_after_session':head_before != command('rev-parse','HEAD').strip()}
    (ROOT/'.guard-runs/review-001-003/verifier-results.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps(record, indent=2))
