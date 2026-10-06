"""Run deterministic local regression groups; no Codex session or API required."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
GROUPS = {
    'unit': ('test_core.py', 'test_policy.py', 'test_host_hook.py', 'test_host_profile.py', 'test_mcp.py'),
    'adversarial': ('test_gateway.py', 'test_shell_git.py', 'test_review_filesystem_fixes.py',
        'test_review_git_fixes.py', 'test_sandbox_edges.py', 'test_write_scope.py', 'test_workflow_003.py'),
    'lifecycle': ('test_hardening.py', 'test_review_lifecycle_fixes.py',
        'test_review_verifier_fixes.py', 'test_final_failures.py'),
    'scale': ('test_scale_git_metadata.py', 'test_scale_search.py', 'test_workspace_scan.py'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', choices=[*GROUPS, 'full'], default='full')
    parser.add_argument('--evidence')
    args = parser.parse_args()
    patterns = GROUPS.get(args.group, ('test*.py',))
    suite = unittest.TestSuite(unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern=pattern)
                               for pattern in patterns)
    started = time.perf_counter()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    # Unsupported backend tests must not be silently skipped into green CI.
    passed = result.wasSuccessful() and result.testsRun > 0 and not result.skipped
    paths = [ROOT/'pyproject.toml', *sorted((ROOT/'guarded_agent').glob('*.py')),
             *sorted((ROOT/'scripts').glob('*.py')), *sorted((ROOT/'tests').glob('*.py')),
             *sorted((ROOT/'examples').rglob('*.py')), *sorted((ROOT/'examples').rglob('*.c'))]
    record = {'date':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'group':args.group, 'policy_versions':'per-test fixture; not a single active policy',
        'python':platform.python_version(), 'platform':platform.platform(),
        'head_commit':subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
        'working_tree':'modified' if subprocess.check_output(
            ['git', '-C', str(ROOT), 'status', '--porcelain'], text=True).strip() else 'clean',
        'source_sha256':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        'tests':result.testsRun, 'failures':[case.id() for case, _ in result.failures],
        'errors':[case.id() for case, _ in result.errors], 'skipped':[case.id() for case, _ in result.skipped],
        'passed':passed, 'elapsed_seconds':round(time.perf_counter()-started, 3)}
    if args.evidence:
        target = Path(args.evidence)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(record, indent=2)+'\n')
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
