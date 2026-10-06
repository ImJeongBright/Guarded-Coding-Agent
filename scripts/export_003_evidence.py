"""Retain reviewed 003 traces, patches, sources, failures and phase measurements."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from guarded_agent.audit import redact
from guarded_agent.filesystem import Filesystem
from export_002_evidence import project

def stats(values):
    values=sorted(values)
    return {'samples':len(values),'median':round(statistics.median(values),3),
            'p95':round(values[math.ceil(len(values)*.95)-1],3),'max':round(max(values),3)} if values else None

def export(base,output,regression_path):
    output.mkdir(parents=True,exist_ok=False)
    def copy_json(source,target):
        target.write_text(json.dumps(project(json.loads(source.read_text()),base),ensure_ascii=False,indent=2)+'\n')
    def copy_lines(source,target):
        target.write_text(''.join(json.dumps(project(json.loads(line),base),ensure_ascii=False)+'\n' for line in source.read_text().splitlines()))
    workloads=[]; all_calls=[]; original_integrity={}
    for kind in ('c','domain'):
        case=base/kind; destination=output/kind; destination.mkdir()
        baseline=json.loads((case/'baseline.json').read_text()); setup=json.loads((case/'setup.json').read_text())
        original=Path(baseline['source']); original_integrity[kind]={}
        for rel,expected in baseline['source_hashes'].items():
            actual=hashlib.sha256((original/rel).read_bytes()).hexdigest()
            original_integrity[kind][rel]=actual==expected
            if actual!=expected: raise ValueError('Original source changed: '+str(original/rel))
            target=destination/'baseline-source'/rel; target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((original/rel).read_bytes())
        for filename in ('baseline.json','setup.json'):
            copy_json(case/filename,destination/filename)
        if kind=='domain': copy_json(case/'golden.json',destination/'golden.json')
        copy_json(case/'operator-state/policy.json',destination/'policy.json')
        copy_lines(case/'operator-state/audit.jsonl',destination/'audit.jsonl')
        work=case/'workspace'; fs=Filesystem(work)
        tracked=subprocess.check_output(['/Library/Developer/CommandLineTools/usr/bin/git','-C',str(work),'ls-files','-z']).decode().split('\0')
        for rel in tracked:
            if not rel: continue
            fs.relative(rel)
            target=destination/'final-source'/rel; target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((work/rel).read_bytes())
        tasks=[]
        for number in (1,2,3):
            session=case/f'task-{number}'; target=destination/f'task-{number}'; target.mkdir()
            verified=json.loads((case/f'verification-{number}.json').read_text())
            if not verified['passed']: raise ValueError('Independent task check failed.')
            copy_json(case/f'verification-{number}.json',target/'verification.json')
            for filename in ('preflight.json','invocation.json','exit.json'):
                copy_json(session/filename,target/filename)
            copy_lines(session/'events.jsonl',target/'events.jsonl')
            (target/'prompt.txt').write_text(project((session/'prompt.txt').read_text(),base))
            (target/'stderr.txt').write_text(project((session/'stderr.txt').read_text(),base))
            commit=verified['git_history']['stdout'].split()[0]
            patch=subprocess.check_output(['/Library/Developer/CommandLineTools/usr/bin/git','-C',str(work),'show','--format=fuller','--no-ext-diff','--no-textconv',commit],text=True)
            (target/'result.patch').write_text(project(patch,base))
            test=next(check for check in verified['checks'] if check['label']=='project tests')
            match=re.search(r'(?:Ran (\d+) tests?|(?:ℹ|#) tests (\d+))',test['stdout']+'\n'+test['stderr'])
            count=int(next(v for v in match.groups() if v)) if match else None
            calls=verified['calls']; all_calls.extend(calls)
            executions=[c for c in calls if c['result'].get('executed')]
            failures=[c for c in executions if c['result'].get('exit_code')!=0]
            timings=[c['result']['timings_ms'] for c in calls if 'timings_ms' in c['result']]
            tasks.append({'task':number,'commit':commit,'project_tests':count,'calls':len(calls),
                'decisions':verified['decisions'],'execution_nonzero_count':len(failures),
                'independent_passed':True,'clean_commit':True,'x_feedback':verified['model_final'],
                'phase_ms':{key:stats([t[key] for t in timings]) for key in ('normalization','decision','audit','execution','total','other')},
                'boundary_ms':stats([t['total']-t['execution'] for t in timings])})
        workloads.append({'kind':kind,'baseline_probes':len(baseline['baseline_requests']),
            'baseline_denials':sum(p['result']['decision']=='DENY' for p in baseline['baseline_requests']),
            'same_request_allow_after':sum(p['result']['decision']=='ALLOW' for p in setup['same_request_replay']),
            'profile_ids':[c['id'] for c in setup['candidate']['commands']],
            'automated_discovery_apply_seconds':round(setup['discovery_seconds']+setup['apply_seconds'],4),
            'agent_operator_review_elapsed_seconds':round(setup['agent_operator_review_elapsed_seconds'],3),
            'human_operator_review_measured':False,'tasks':tasks})
    regression=json.loads(regression_path.read_text())
    if not regression['passed']: raise ValueError('Final regression failed.')
    for source in sorted(base.glob('regression-*.json')): copy_json(source,output/source.name)
    if (base/'workflow-refinements.json').exists(): copy_json(base/'workflow-refinements.json',output/'workflow-refinements.json')
    legacy=ROOT/'.guard-runs/user-x-003'
    legacy_target=output/'legacy-scripted-x'; legacy_target.mkdir()
    for name in ('summary.json','trace.json'): copy_json(legacy/name,legacy_target/name)
    copy_lines(legacy/'state/audit.jsonl',legacy_target/'audit.jsonl')
    files=subprocess.check_output(['rg','--files','guarded_agent','scripts','tests','examples'],cwd=ROOT,text=True).splitlines()
    manifest={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in sorted(files)}
    (output/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    decisions={key:sum(c['result'].get('decision')==key for c in all_calls) for key in ('ALLOW','DENY','REQUIRE_APPROVAL')}
    per_tool={}
    for tool in ('guard_filesystem','guard_shell','guard_git'):
        values=[c['result']['timings_ms'] for c in all_calls if c['tool']==tool and c['result'].get('decision')=='ALLOW']
        per_tool[tool]={'calls':len(values),'boundary_ms':stats([v['total']-v['execution'] for v in values]),
                       'execution_ms':stats([v['execution'] for v in values])}
    summary={'exported_at':datetime.now(timezone.utc).isoformat(),'base_commit':'b93ba56',
        'working_tree':'uncommitted implementation','codex_version':'0.160.0','persona':'X: six actual model sessions',
        'workloads':workloads,'live_calls':len(all_calls),'live_decisions':decisions,'phase_by_tool':per_tool,
        'full_regression':regression,'original_source_integrity':original_integrity,
        'legacy_scripted_x':project(json.loads((legacy/'summary.json').read_text()),base),
        'profile_registrations':2,'profile_reregistrations_between_tasks':0,'local_approvals':decisions['REQUIRE_APPROVAL'],
        'known_usability_denial':{'count':1,'request':'C task 2 search query="" glob=AGENTS.md',
            'classification':'missing file-path discovery semantics','fixed':True},
        'remaining_false_denials_observed_after_fix':0,
        'long_term_real_user_evaluation':'not measured',
        'timing_definition':'Returned perf_counter phases include both normalizations; boundary=total-execution. Git state queries are in normalization. Model/transport time excluded.',
        'limitations':['Two dependency-free ordinary repositories, no package installation or network',
            'Baseline is 11 identical request probes plus existing tests, not a pre-change full model session',
            'Agent-reviewed setup time; actual human review time not measured','Only macOS/Codex CLI 0.160.0 profile',
            'Optimistic edit hash checks are not OS-level CAS against concurrent external writers','No longitudinal user satisfaction measurement']}
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'evidence':str(output),'calls':len(all_calls),'decisions':decisions,'regression':regression['tests']}))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--root',required=True); p.add_argument('--output',required=True)
    p.add_argument('--regression',required=True); a=p.parse_args()
    export(Path(a.root).resolve(),Path(a.output).resolve(),Path(a.regression).resolve())
