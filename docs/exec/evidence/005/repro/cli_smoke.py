"""Exercise the documented operator CLI on a disposable C workspace; no model.

Run on a macOS host that permits Guard's own Seatbelt backend:
python3 docs/exec/evidence/005/repro/cli_smoke.py --output <new directory>
"""
import argparse
import datetime
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    base = Path(args.output).resolve()
    base.mkdir(parents=True, exist_ok=False)
    work, state = base/'workspace', base/'state'
    shutil.copytree(ROOT/'examples/c-dbms', work)
    (work/'build').mkdir()
    record = {
        'date': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'kind': 'README operator CLI smoke; no model session',
        'head_commit': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
        'platform': platform.platform(), 'python': platform.python_version(),
        'checks': [], 'passed': False,
    }

    def cli(*argv, request=None):
        result = subprocess.run([sys.executable, '-m', 'guarded_agent', *argv],
            cwd=ROOT, input=json.dumps(request) if request is not None else None,
            text=True, capture_output=True, timeout=130)
        value = json.loads(result.stdout) if result.stdout else None
        record['checks'].append({'command': list(argv), 'returncode': result.returncode,
                                 'response': value, 'stderr': result.stderr})
        if result.returncode:
            raise RuntimeError('CLI command failed: '+argv[0])
        return value

    try:
        cli('init', '--workspace', str(work), '--state', str(state))
        candidate = cli('discover', '--workspace', str(work), '--state', str(state))
        ids = [item['id'] for item in candidate['commands']]
        assert ids == ['c-build', 'c-tests', 'c-db'], ids
        # This trusted fixture reviews exact repository-defined C capabilities.
        cli('profile-apply', '--workspace', str(work), '--state', str(state),
            '--reviewed-digest', candidate['digest'], '--ids', *ids)
        config = state/'codex.example.toml'
        subprocess.run([sys.executable, str(ROOT/'scripts/make_host_config.py'),
            '--workspace', str(work), '--state', str(state), '--output', str(config)],
            cwd=ROOT, capture_output=True, text=True, check=True, timeout=10)
        parsed = tomllib.loads(config.read_text())
        assert parsed['sandbox_mode'] == 'read-only'
        record['config_toml_valid'] = True
        for profile in ('c-build', 'c-tests'):
            result = cli('exec', '--workspace', str(work), '--state', str(state),
                '--run-id', 'readme-smoke', request={'tool':'shell', 'operation':'run', 'profile':profile})
            assert result['executed'] and result['exit_code'] == 0 and not result.get('audit_error'), result
        from guarded_agent.host import preflight
        record['codex_preflight_version'] = preflight(work, state)['codex_version']
        record['passed'] = True
    except Exception as error:
        record['error'] = str(error)
    (base/'results.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps({key:value for key,value in record.items() if key != 'checks'}, indent=2))
    return 0 if record['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
