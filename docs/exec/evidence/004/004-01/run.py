"""Post-004-01 generated M1/M2 capacity smoke check; trusted fixture setup only."""
import json
import platform
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from guarded_agent.domain import MAX_GIT_METADATA_OUTPUT, MAX_OUTPUT
from guarded_agent.gateway import Gateway

GIT='/Library/Developer/CommandLineTools/usr/bin/git'
def raw(work,*args):
    return subprocess.run([GIT,'-C',str(work),*args],check=True,capture_output=True).stdout

def exercise(name,tracked_count,ignored_count):
    case=BASE/name;work=case/'workspace';work.mkdir(parents=True)
    (work/'.gitignore').write_text('build/\n')
    target=''
    for i in range(tracked_count):
        target=f'src/module_{i//100:03}/component_{i:05}.c'
        file=work/target;file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text(f'int source_{i:05} = {i%7};\n')
    subprocess.run([GIT,'init','-b','feature/'+name,str(work)],check=True,capture_output=True)
    raw(work,'add','--','.gitignore','src')
    raw(work,'-c','user.name=Scale Fixture','-c','user.email=scale@example.invalid',
        '-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false','commit','-m','Generated scale baseline')
    (work/'build').mkdir()
    for i in range(ignored_count):
        (work/'build'/f'generated_{i:06}.txt').write_text('ignored fixture\n')
    (work/target).write_text(f'int source_{tracked_count-1:05} = changed;\n/* SCALE_POST_004 */\n')
    path_bytes=len(raw(work,'ls-files','-z'))
    argv=[str(Path(sys.executable).resolve()),'-B','-c','print("guard-medium-ok")']
    gateway=Gateway(work,case/'operator-state',{'version':'scale-post-004-01',
        'commands':[{'argv':argv}],'git_remotes':{}})
    requests=[
       ('git_status',dict(tool='git',operation='status')),
       ('single_file_diff',dict(tool='git',operation='diff',paths=[target])),
       ('shell_noop',dict(tool='shell',operation='exec',argv=argv)),
       ('root_search',dict(tool='filesystem',operation='search',path='.',query='SCALE_POST_004',glob='*.c')),
       ('module_search',dict(tool='filesystem',operation='search',path=str(Path(target).parent),query='SCALE_POST_004',glob='*.c'))]
    calls={}
    for label,request in requests:
        started=time.perf_counter();result=gateway.submit(request)
        calls[label]={'wall_ms':round((time.perf_counter()-started)*1000,3),'result':result}
        print(json.dumps({'case':name,'operation':label,'decision':result['decision'],
           'rule':result['matched_rule'],'ms':calls[label]['wall_ms'],
           'incomplete':result.get('incomplete'),'matches':len(result.get('matches',[]))}),flush=True)
    record={'case':name,'tracked_source_files':tracked_count,'ignored_build_files':ignored_count,
        'tracked_path_bytes':path_bytes,'metadata_limit_bytes':MAX_GIT_METADATA_OUTPUT,
        'user_output_limit_bytes':MAX_OUTPUT,'platform':platform.platform(),'python':platform.python_version(),
        'target':target,'calls':calls}
    (case/'result.json').write_text(json.dumps(record,indent=2)+'\n')
    return record

results=[exercise('M1-3000-10000',3000,10000),exercise('M2-10000-25000',10000,25000)]
(BASE/'summary.json').write_text(json.dumps({'kind':'post-004-01 synthetic capacity smoke',
    'files_are_generated_fixtures':True,'repeats_per_operation':1,'results':[
       {k:v for k,v in record.items() if k!='calls'}|{'calls':{
        name:{'wall_ms':call['wall_ms'],'decision':call['result']['decision'],
        'matched_rule':call['result']['matched_rule'],'incomplete':call['result'].get('incomplete'),
        'matches':len(call['result'].get('matches',[]))} for name,call in record['calls'].items()}}
        for record in results]},indent=2)+'\n')
print('M1/M2 post-change capacity smoke complete.',flush=True)
