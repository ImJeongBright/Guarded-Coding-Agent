"""Project reviewed fixture evidence into portable docs; never export host auth/log DBs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from pathlib import Path
import statistics
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from guarded_agent.audit import redact


def project(value, run):
    replacements=[(str(run),'$RUN'),(str(ROOT),'$REPO'),(str(Path.home()),'$HOME')]
    def visit(item):
        if isinstance(item,dict): return {k:visit(v) for k,v in item.items()}
        if isinstance(item,list): return [visit(v) for v in item]
        if isinstance(item,str):
            for original,placeholder in replacements: item=item.replace(original,placeholder)
        return item
    return visit(redact(value))


def export(output):
    output=Path(output).resolve(); output.mkdir(parents=True,exist_ok=False)
    def json_copy(source,target,run):
        value=project(json.loads(source.read_text()),run)
        target.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    def lines_copy(source,target,run):
        value=[project(json.loads(line),run) for line in source.read_text().splitlines()]
        target.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in value))
    workloads=[]
    for kind in ['c','python','javascript']:
        base=ROOT/'.guard-runs'/('live-'+kind+'-01')
        destination=output/kind; destination.mkdir()
        verified=json.loads((base/'verification.json').read_text())
        if not verified['passed']: raise ValueError('Independent verification did not pass: '+kind)
        test_output='\n'.join(x.get('stdout','')+'\n'+x.get('stderr','') for x in verified['checks'] if x['kind']=='project tests/build')
        match=re.search(r'(?:Ran (\d+) tests?|(?:ℹ|#) tests (\d+))',test_output)
        if match is None: raise ValueError('Project test count missing: '+kind)
        test_count=int(next(value for value in match.groups() if value))
        for source,target in [('verification.json','verification.json'),('state/policy.json','policy.json'),
                              ('session/preflight.json','preflight.json'),('session/invocation.json','invocation.json')]:
            json_copy(base/source,destination/target,base)
        if (base/'baseline.json').exists():
            json_copy(base/'baseline.json',destination/'baseline.json',base)
        lines_copy(base/'session/events.jsonl',destination/'events.jsonl',base)
        lines_copy(base/'state/audit.jsonl',destination/'audit.jsonl',base)
        (destination/'prompt.txt').write_text(project((base/'prompt.txt').read_text(),base))
        patch=subprocess.check_output(['/usr/bin/git','-C',str(base/'workspace'),'diff','--no-ext-diff','--no-textconv','HEAD~','HEAD'],text=True)
        (destination/'result.patch').write_text(project(patch,base))
        events=[json.loads(x) for x in (base/'state/audit.jsonl').read_text().splitlines()]
        decisions={e['event_id']:e for e in events if e['phase']=='decision'}
        latencies=sorted((e['timestamp']-decisions[e['parent']]['timestamp'])*1000 for e in events if e['phase']=='result')
        workloads.append({'kind':kind,'calls':verified['model_tool_calls'],'decisions':verified['decisions'],
                          'project_tests':test_count,'independent_passed':True,'clean_local_commit':True,
                          'decision_to_result_ms':{'median':round(statistics.median(latencies),3),
                            'p95':round(latencies[math.ceil(len(latencies)*0.95)-1],3),'max':round(max(latencies),3)},
                          'audit_span_seconds':round(events[-1]['timestamp']-events[0]['timestamp'],3),
                          'commit':verified['git_history']['stdout'].split()[0]})
    probes=[]
    for name in ['native-01','native-02','native-03','missing-01','crash-01','timeout-01','mcp-down-01','unsafe-control-01','mcp-dies-01']:
        base=ROOT/'.guard-runs'/('probe-'+name)
        destination=output/'probes'/name; destination.mkdir(parents=True)
        for filename in ['summary.json','invocation.json']:
            json_copy(base/filename,destination/filename,base)
        lines_copy(base/'events.jsonl',destination/'events.jsonl',base)
        (destination/'stderr.txt').write_text(project((base/'stderr.txt').read_text(),base))
        probes.append(json.loads((base/'summary.json').read_text()))
    x=ROOT/'.guard-runs/user-x-09'; (output/'scripted-x').mkdir()
    json_copy(x/'summary.json',output/'scripted-x/summary.json',x)
    lines_copy(x/'state/audit.jsonl',output/'scripted-x/audit.jsonl',x)
    json_copy(x/'trace.json',output/'scripted-x/trace.json',x)
    files=subprocess.check_output(['rg','--files','guarded_agent','scripts','tests','examples'],cwd=ROOT,text=True).splitlines()
    manifest={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in sorted(files)}
    (output/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    summary={'exported_at':datetime.now(timezone.utc).isoformat(),'base_commit':'b93ba56',
             'working_tree':'uncommitted implementation','policy_version':'001','codex_version':'0.160.0',
             'model_override':None,'persona':'X; live Codex model, disposable development repositories',
             'workloads':workloads,'normal_calls':sum(w['calls'] for w in workloads),
             'normal_denials':sum(w['decisions'].get('DENY',0) for w in workloads),
             'normal_approvals':sum(w['decisions'].get('REQUIRE_APPROVAL',0) for w in workloads),'probes':probes,
             'full_regression':json.loads((ROOT/'docs/exec/evidence/regression-002-final.json').read_text()),
             'long_term_evaluation':'not measured','limitations':['Preconfigured small tasks; no dependency install',
                 'Only this Codex CLI/macOS host profile','No real-user longitudinal feedback',
                 'Audit decision-to-result latency excludes normalization, model generation and host startup']}
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'evidence':str(output),'normal_calls':summary['normal_calls'],'tests':summary['full_regression']['tests']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',required=True)
    args=parser.parse_args(); export(args.output)
