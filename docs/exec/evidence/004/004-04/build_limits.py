"""Exercise actual bounded C build, timeout, output and file-size controls."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
BASE=Path(__file__).resolve().parent/'build-scope'
WORK=BASE/'workspace'
STATE=BASE/'operator-state'
WORK.mkdir(parents=True,exist_ok=True)
(WORK/'src').mkdir(exist_ok=True)
(WORK/'build').mkdir(exist_ok=True)
cc=subprocess.check_output(['/usr/bin/xcrun','--find','cc'],text=True).strip()
sdk=subprocess.check_output(['/usr/bin/xcrun','--show-sdk-path'],text=True).strip()
source='''#include <stdio.h>
int main(void) {
    FILE *db = fopen("build/result.db", "w");
    if (db == NULL) return 2;
    fputs("record=1\\n", db);
    if (fclose(db) != 0) return 3;
    puts("dbms-build-ok");
    return 0;
}
'''
(WORK/'src/main.c').write_text(source)
build_argv=[cc,'-isysroot',sdk,'-std=c11','-Wall','-Wextra','-Werror','-pedantic','src/main.c','-o','build/minidb']
run_argv=[str(WORK/'build/minidb')]
python=str(Path(sys.executable).resolve())
big_output=[python,'-B','-c','import sys; sys.stdout.write("x"*100000)']
oversize=[python,'-B','-c','from pathlib import Path; Path("build/oversized.bin").write_bytes(b"x"*(33*1024*1024))']
slow=[python,'-B','-c','import time; time.sleep(2)']
policy={'version':'scale-build-004-04','commands':[
    {'id':'build','argv':build_argv,'write_paths':['build'],'timeout':20},
    {'id':'run','argv':run_argv,'write_paths':['build'],'timeout':20},
    {'id':'output','argv':big_output,'write_paths':[],'timeout':20},
    {'id':'oversize','argv':oversize,'write_paths':['build'],'timeout':20},
    {'id':'timeout','argv':slow,'write_paths':[],'timeout':0.25},
]}
from guarded_agent.gateway import Gateway
gateway=Gateway(WORK,STATE,policy)

def call(label,argv):
    started=time.perf_counter()
    result=gateway.submit({'tool':'shell','operation':'exec','argv':argv})
    elapsed=round((time.perf_counter()-started)*1000,3)
    return {'label':label,'elapsed_ms':elapsed,
        'decision':result['decision'],'matched_rule':result['matched_rule'],
        'executed':result['executed'],'exit_code':result['exit_code'],
        'timed_out':result.get('timed_out',False),
        'output_truncated':result.get('output_truncated',False),
        'stdout_bytes':len(result.get('stdout','').encode()),
        'stderr_bytes':len(result.get('stderr','').encode()),
        'stdout':result.get('stdout','')[:400],
        'stderr':result.get('stderr','')[:400],
        'execution_status':result.get('execution_status'),
        'lifecycle_status':result.get('lifecycle_status')}

results=[]
results.append(call('actual_cc_build',build_argv))
binary_path=WORK/'build/minidb'
if binary_path.exists():
    results[-1]['binary_bytes']=binary_path.stat().st_size
else:
    results[-1]['binary_bytes']=0
    (BASE/'build-limits.json').write_text(json.dumps({'results':results},indent=2)+'\n')
    raise RuntimeError('The declared C build profile failed; see build-limits.json for its captured output.')
results.append(call('run_built_c_dbms',run_argv))
results[-1]['database_bytes']=(WORK/'build/result.db').stat().st_size
results.append(call('stdout_limit_100000_bytes',big_output))
results.append(call('file_limit_attempt_33_mib',oversize))
oversized_path=WORK/'build/oversized.bin'
results[-1]['partial_file_bytes']=oversized_path.stat().st_size if oversized_path.exists() else 0
results.append(call('profile_timeout_250_ms',slow))
record={'kind':'004-04 actual local guarded C compile and resource-bound probes',
    'platform':platform.platform(),'python':platform.python_version(),
    'workspace':str(WORK),'cc':cc,'cc_resolved':str(Path(cc).resolve()),'sdk':sdk,
    'source_sha256':hashlib.sha256((WORK/'src/main.c').read_bytes()).hexdigest(),
    'file_size_limit_bytes':32*1024*1024,'stdout_limit_bytes':64000,
    'profile_max_timeout_seconds':120,'results':results,
    'binary_sha256':hashlib.sha256((WORK/'build/minidb').read_bytes()).hexdigest()}
(BASE/'build-limits.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'cc':record['cc_resolved'],'results':results},indent=2),flush=True)
