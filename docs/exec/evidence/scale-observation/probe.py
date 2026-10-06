"""Capacity observation using generated repositories, not real medium applications."""
import collections
import json
import platform
from pathlib import Path
import statistics
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from guarded_agent.gateway import Gateway
from guarded_agent.domain import MAX_OUTPUT

BASE=Path(__file__).resolve().parent
GIT='/Library/Developer/CommandLineTools/usr/bin/git'
def git(work,*args):
    return subprocess.check_output([GIT,'-C',str(work),*args])
def create(name,count,ignored=0):
    case=BASE/name;work=case/'workspace';work.mkdir(parents=True)
    (work/'.gitignore').write_text('build/\n')
    paths=[]
    for i in range(count):
        relative=f'src/module_{i//100:03}/subsystem/component_{i:06}.c'
        p=work/relative;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text('/* generated capacity fixture */\n'*80+'int generated_value = 0;\n')
        paths.append(relative)
    subprocess.run([GIT,'init','-b','feature/scale',str(work)],check=True,capture_output=True)
    git(work,'add','--','.gitignore','src')
    git(work,'-c','user.name=Capacity Fixture','-c','user.email=capacity@example.invalid',
        '-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false','commit','-m','Generated capacity baseline')
    if ignored:
        (work/'build').mkdir()
        for i in range(ignored):(work/'build'/f'generated_{i:06}.txt').write_text('ignored output\n')
    target=paths[-1]
    (work/target).write_text((work/target).read_text().replace('= 0;','= 1;')+'/* SCALE_UNIQUE_NEEDLE */\n')
    argv=[str(Path(sys.executable).resolve()),'-B','-c','print("guard-scale-ok")']
    gateway=Gateway(work,case/'operator-state',{'version':'scale-observation-001',
        'commands':[{'argv':argv}],'git_remotes':{}})
    requests={
        'read_one_file':dict(tool='filesystem',operation='read',path=target),
        'shell_noop':dict(tool='shell',operation='exec',argv=argv),
        'git_status':dict(tool='git',operation='status'),
        'git_diff_one_file':dict(tool='git',operation='diff',paths=[target])}
    calls={}
    for label,request in requests.items():
        calls[label]=[]
        for repeat in range(3):
            result=gateway.submit(request)
            calls[label].append(result)
        print(json.dumps({'case':name,'operation':label,'decision':result['decision'],
            'rule':result['matched_rule'],'median_ms':round(statistics.median(r['timings_ms']['total'] for r in calls[label]),3)}),flush=True)
    for label,scope in (('search_root','.'),('search_target_module',str(Path(target).parents[1]))):
        calls[label]=[gateway.submit(dict(tool='filesystem',operation='search',path=scope,
            query='SCALE_UNIQUE_NEEDLE',glob='*.c'))]
    summary={label:{'samples':len(results),
        'decisions':dict(collections.Counter(r['decision'] for r in results)),
        'rules':dict(collections.Counter(r['matched_rule'] for r in results)),
        'total_median_ms':round(statistics.median(r['timings_ms']['total'] for r in results),3),
        'total_max_ms':round(max(r['timings_ms']['total'] for r in results),3),
        'normalization_median_ms':round(statistics.median(r['timings_ms']['normalization'] for r in results),3),
        'incomplete':results[-1].get('incomplete'),
        'truncation_reasons':results[-1].get('truncation_reasons'),
        'matches':len(results[-1].get('matches',[])),
        'scanned_entries':results[-1].get('scanned_entries'),
        'scanned_bytes':results[-1].get('scanned_bytes')}
        for label,results in calls.items()}
    record={'case':name,'source_files':count,'generated_source_lines':count*81+1,
        'ignored_files':ignored,'tracked_paths':len(git(work,'ls-files','-z').split(b'\0'))-1,
        'raw_index_path_bytes':len(git(work,'ls-files','-z')),'tool_output_limit_bytes':MAX_OUTPUT,
        'calls':calls,'summary':summary}
    (case/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    return record

records=[]
for case,count,ignored in [('small-100',100,0),('medium-1000',1000,0),
                           ('medium-3000',3000,0),('medium-1000-ignored',1000,10000)]:
    records.append(create(case,count,ignored))
(BASE/'summary.json').write_text(json.dumps({'kind':'synthetic capacity probe',
    'platform':platform.platform(),'python':platform.python_version(),
    'samples_per_repeated_operation':3,'source_file_lines':81,
    'cases':[{k:v for k,v in r.items() if k!='calls'} for r in records]},indent=2)+'\n')
print('Capacity observation complete.',flush=True)
