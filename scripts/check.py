"""Run meaningful regression checks and optionally retain a machine-readable record."""
import argparse
import datetime
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
parser=argparse.ArgumentParser()
parser.add_argument('--evidence')
args=parser.parse_args()
suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
started=time.perf_counter()
result=unittest.TextTestRunner(verbosity=2).run(suite)
record={'date':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'policy_version':'001','python':platform.python_version(),'platform':platform.platform(),
        'base_commit':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','--short','HEAD'],text=True).strip(),
        'working_tree':'uncommitted MVP implementation','tests':result.testsRun,
        'failures':[case.id() for case,_ in result.failures],'errors':[case.id() for case,_ in result.errors],
        'skipped':[case.id() for case,_ in result.skipped],'passed':result.wasSuccessful(),
        'elapsed_seconds':round(time.perf_counter()-started,3)}
if args.evidence:
    target=Path(args.evidence)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(record,indent=2)+'\n')
raise SystemExit(0 if result.wasSuccessful() else 1)
