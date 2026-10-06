"""Copy existing dependency-free projects; original repositories are read-only."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from guarded_agent.gateway import Gateway

DOMAIN=ROOT.parent/'MoneyPilot_Backend/packages/domain'
TASKS={
 'c':[
  'Add `find <uint32 id>` to the C DBMS. Print exactly `(id, name)` when found and `Not found.` otherwise. Reject malformed/negative/overflow/extra arguments without changing data. Preserve insert/select/count and GDB1 format. Add tests and README. Use a selected test filter for the new feature, then full tests. Compile release and debug, inspect staged diff, and commit locally.',
  'Refactor row output so select and find share a small helper. Preserve exact outputs and persistence behavior. Use bounded search/read and hash-bound edit when appropriate, run selected find tests and the full suite, inspect staged diff, and commit locally.',
  'Strengthen find regression coverage for empty database, zero/max ids, duplicate inserts, restart persistence, missing ids and invalid syntax. Confirm read-only find never creates or changes the database. Update README if useful. Run filtered and full tests, inspect staged diff, and commit locally.'
 ],
 'domain':[
  'Fix evaluateDecision input validation: openedSources must be a nonnegative safe integer; otherwise throw RangeError before producing feedback. Preserve valid-input scoring. Add regression tests, document it, run a selected openedSources test filter and all tests, inspect staged diff and commit locally.',
  'Refactor forecast classification into exported directionForChange(change, key). Return null for null/undefined/non-finite change, otherwise preserve the existing up/flat/down thresholds. Reuse it in evaluateDecision, treating unknown actual changes as actual=null, correct=null and no prediction points when any actual result is unknown. Add tests, preserve valid-input results, inspect staged diff and commit locally.',
  'Add deterministic boundary/property regression cases for source counts (including 0 and MAX_SAFE_INTEGER), malformed counts, direction threshold boundaries and non-finite actual changes. Confirm valid feedback scores stay within 0..100 and input objects are unchanged. Update documentation, run selected validation tests and all tests, inspect staged diff and commit locally.'
 ]}


def main():
 p=argparse.ArgumentParser(); p.add_argument('--output',required=True); a=p.parse_args()
 base=Path(a.output).resolve(); base.mkdir(parents=True,exist_ok=False)
 for kind in ['c','domain']:
  started=time.perf_counter(); case=base/kind; case.mkdir(); work=case/'workspace'; work.mkdir()
  source=ROOT/'examples/c-dbms' if kind=='c' else DOMAIN
  files=['Makefile','README.md','src/db.c','tests/test_db.py','.gitignore'] if kind=='c' else ['package.json','README.md','src/simulation.ts','src/decision-feedback.ts','src/annual-scenario.ts','test/simulation.test.mjs']
  hashes={}
  for rel in files:
   original=source/rel
   if original.is_symlink() or not original.is_file(): raise ValueError('Expected ordinary source: '+str(original))
   target=work/rel; target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(original,target)
   hashes[rel]=hashlib.sha256(original.read_bytes()).hexdigest()
  if kind=='c': (work/'build').mkdir()
  else: (work/'.gitignore').write_text('__pycache__/\n')
  subprocess.run([sys.executable,'-m','guarded_agent','init','--workspace',str(work),'--state',str(case/'state'),*(['--c-dbms'] if kind=='c' else [])],cwd=ROOT,capture_output=True,check=True)
  policy=json.loads((case/'state/policy.json').read_text())
  if kind=='domain': policy['commands']=[{'argv':[str(Path(shutil.which('node')).resolve()),'--experimental-strip-types','--test','test/*.test.mjs']}]
  (case/'state/policy.json').write_text(json.dumps(policy,indent=2))
  git=shutil.which('git')
  subprocess.run([git,'init','-b','feature/003-'+kind,str(work)],capture_output=True,check=True)
  subprocess.run([git,'-C',str(work),'add','.'],check=True)
  subprocess.run([git,'-C',str(work),'-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false','-c','user.name=Fixture Setup','-c','user.email=fixture@example.invalid','commit','-m','Existing project snapshot for Guard 003'],capture_output=True,check=True)
  g=Gateway(work,case/'baseline-state',policy,actor='X-baseline')
  sourcefile='src/db.c' if kind=='c' else 'src/decision-feedback.ts'
  text=(work/sourcefile).read_text(); old=text.splitlines()[0]
  testargv=policy['commands'][2 if kind=='c' else 0]['argv']
  filtered=[*testargv,'-k','count'] if kind=='c' else [*testargv[:3],'--test-name-pattern','score',*testargv[3:]]
  probes=[{'tool':'shell','operation':'exec','argv':filtered},
          {'tool':'filesystem','operation':'search','path':'src','query':'parse_id' if kind=='c' else 'evaluateDecision'},
          {'tool':'filesystem','operation':'read','path':sourcefile,'start_line':1,'end_line':20},
          {'tool':'filesystem','operation':'edit','path':sourcefile,'old_text':old,'new_text':old,'expected_sha256':hashlib.sha256(text.encode()).hexdigest()},
          {'tool':'git','operation':'diff','staged':True}]
  if kind=='c':
   debug=policy['commands'][0]['argv'].copy(); debug[debug.index('-O2')]='-O0'; debug.insert(debug.index('-O0')+1,'-g')
   probes.insert(1,{'tool':'shell','operation':'exec','argv':debug})
  results=[{'request':request,'result':g.submit(request)} for request in probes]
  full=[g.submit({'tool':'shell','operation':'exec','argv':command['argv']}) for command in policy['commands'] if not(kind=='c' and len(command['argv'])==1)]
  record={'kind':kind,'source':str(source),'source_hashes':hashes,'baseline_requests':results,'full_checks':full,
          'setup_and_baseline_seconds':round(time.perf_counter()-started,3),'tasks':TASKS[kind]}
  (case/'baseline.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
  print(json.dumps({'kind':kind,'probes_denied':sum(x['result']['decision']=='DENY' for x in results),'baseline_tests_passed':all(x['exit_code']==0 for x in full),'seconds':record['setup_and_baseline_seconds']}),flush=True)


if __name__=='__main__': main()
