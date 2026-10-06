"""Recheck preserved 004 workspaces through current Guard; no model session.

python3 docs/exec/evidence/005/repro/scale_recheck.py --m1 <M1 workspace>
    --m2 <M2 workspace> --output <new operator evidence directory>
Existing operator-state/policy.json is read beside each workspace. All new audit
and results go to output; no historical audit/verification is overwritten.
"""
import argparse
import datetime
import json
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from guarded_agent.gateway import Gateway

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--m1', required=True)
parser.add_argument('--m2', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args()
out = Path(args.output).resolve(); out.mkdir(parents=True, exist_ok=False)
record = {'date':datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'platform':platform.platform(), 'python':platform.python_version(),
          'guard_head':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),
          'kind':'current Guard replay on preserved functional C DBMS + synthetic file volume; no new model session',
          'profiles':{}}
for label, raw in [('M1',args.m1), ('M2',args.m2)]:
    work = Path(raw).resolve(strict=True)
    policy = json.loads((work.parent/'operator-state/policy.json').read_text())
    guard = Gateway(work, out/label, policy, actor='final-independent-recheck')
    def git(*argv):
        return subprocess.check_output([guard.git.executable, '-C', str(work), *argv])
    head = git('rev-parse','HEAD').decode().strip()
    tracked = git('ls-files','-z').split(b'\0')[:-1]
    ignored = git('ls-files','--others','--ignored','--exclude-standard','-z').split(b'\0')[:-1]
    samples = [guard.submit(dict(tool='git',operation='status')) for _ in range(3)]
    checks = [guard.submit(dict(tool='shell',operation='run',profile=name)) for name in ('build','tests')]
    match = re.search(r'Ran (\d+) tests', checks[1]['stderr'])
    item = {'workspace_head':head, 'tracked_files':len(tracked), 'ignored_files':len(ignored),
        'status_samples':samples, 'status_median_ms':statistics.median(x['timings_ms']['total'] for x in samples),
        'build_and_tests':checks, 'project_tests':int(match.group(1)) if match else None,
        'ending_head':git('rev-parse','HEAD').decode().strip(),
        'ending_status':git('status','--porcelain').decode()}
    item['passed'] = (all(x['executed'] and x['exit_code']==0 for x in samples+checks)
                      and not item['ending_status'] and item['ending_head']==head and item['project_tests'] is not None)
    record['profiles'][label] = item
record['passed'] = all(x['passed'] for x in record['profiles'].values())
(out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({key:{k:v for k,v in value.items() if k in ('tracked_files','ignored_files','status_median_ms','project_tests','passed')}
                  for key,value in record['profiles'].items()},indent=2))
raise SystemExit(0 if record['passed'] else 1)
