"""Independent contract checks and per-task live-call evidence for 003."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from guarded_agent.gateway import Gateway
from scripts.session_evidence import validate_session, read_session_events, session_exit

C_CHECK = '''from pathlib import Path
import struct,subprocess,tempfile
root=Path.cwd(); binary=root/'build/minidb'; (root/'build/test-data').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=root/'build/test-data') as tmp:
 path=Path(tmp)
 def run(text):
  r=subprocess.run([str(binary)],input=text,text=True,capture_output=True,cwd=tmp,timeout=3)
  assert r.returncode==0,(r.returncode,r.stderr)
  return r.stdout.splitlines()
 assert run('find 0\\nfind 4294967295\\nfind 1\\n.exit\\n')==['Not found.']*3
 assert not (path/'data.db').exists()
 assert run('insert 0 zero\\ninsert 4294967295 max\\ninsert 12 twelve\\n.exit\\n')==['Executed.']*3
 expected=b'GDB1'+struct.pack('<I',3)+b''.join(struct.pack('<I32s',i,n) for i,n in [(0,b'zero'),(4294967295,b'max'),(12,b'twelve')])
 assert (path/'data.db').read_bytes()==expected
 timestamp=(path/'data.db').stat().st_mtime_ns
 assert run('find 12\\nfind 0\\nfind 4294967295\\nfind 10\\ncount\\n.exit\\n')==['(12, twelve)','(0, zero)','(4294967295, max)','Not found.','Count: 3']
 invalid=['find','find -1','find 4294967296','find 1x','find +0','find 1 extra','find 1 extra more','find 1.0','find 99999999999999999999999999999999999']
 assert run('\\n'.join(invalid)+'\\n.exit\\n')==['Error: invalid statement.']*len(invalid)
 assert run('insert 12 other\\nfind 12\\n.exit\\n')==['Error: duplicate id.','(12, twelve)']
 assert (path/'data.db').read_bytes()==expected
 assert (path/'data.db').stat().st_mtime_ns==timestamp
 assert not (path/'data.db.tmp').exists()
 assert run('select\\n.exit\\n')==['(0, zero)','(4294967295, max)','(12, twelve)','Executed.']
print('Independent C contract passed: exact find, empty/read-only, malformed, uint32, duplicate, restart, select, GDB1')
'''

GOLDEN = '''import fs from 'node:fs';
import {evaluateDecision} from './src/decision-feedback.ts';
const inputs=JSON.parse(fs.readFileSync(0,'utf8'));
console.log(JSON.stringify(inputs.map(input=>{const f=evaluateDecision(input);return {score:f.score,forecasts:f.forecasts};})));
'''

DOMAIN_CHECK = '''import fs from 'node:fs';
import assert from 'node:assert/strict';
import * as feedback from './src/decision-feedback.ts';
const {task,inputs,golden}=JSON.parse(fs.readFileSync(0,'utf8'));
for(let i=0;i<inputs.length;i++) {
 const input=inputs[i], before=structuredClone(input), actual=feedback.evaluateDecision(input);
 assert.deepEqual({score:actual.score,forecasts:actual.forecasts},golden[i]);
 assert.deepEqual(input,before);
 assert.ok(Object.values(actual.score).every(n=>Number.isFinite(n)&&n>=0&&n<=100));
}
for(const count of [-1,0.5,NaN,Infinity,-Infinity,Number.MAX_SAFE_INTEGER+1,null,undefined,'1',true]) {
 const input={...inputs[0],openedSources:count};
 assert.throws(()=>feedback.evaluateDecision(input),RangeError);
}
if(task>=2) {
 const direction=feedback.directionForChange;
 for(const key of ['S&P 500','US 10Y Treasury yield']) {
  const t=key.includes('10Y')?1:0.05;
  for(const [value,expected] of [[-t-0.001,'down'],[-t,'flat'],[0,'flat'],[t,'flat'],[t+0.001,'up'],[null,null],[undefined,null],[NaN,null],[Infinity,null],[-Infinity,null]]) assert.equal(direction(value,key),expected);
 }
 for(const value of [NaN,Infinity,-Infinity,null,undefined]) {
  const input=structuredClone(inputs[0]); input.actualChanges['S&P 500']=value;
  const before=structuredClone(input), actual=feedback.evaluateDecision(input);
  assert.equal(actual.forecasts[0].actual,null); assert.equal(actual.forecasts[0].correct,null);
  assert.equal(actual.score.prediction,0); assert.deepEqual(input,before);
 }
}
console.log('Independent domain contract passed: valid-score compatibility, malformed counts, bounds, immutability'+(task>=2?', finite thresholds and unknown forecasts':''));
'''

def inputs():
    keys=['S&P 500','NASDAQ-100','US 10Y Treasury yield','Broad U.S. Dollar Index']
    return [dict(marketIndex=market,predictions=dict(zip(keys,['down','flat','up','up'])),
        reason=reason,action='defensive' if count%2 else 'keep',openedSources=count,
        actualChanges=dict(zip(keys,[-0.95,0,19,0.72])))
        for market in range(3) for count,reason in [(0,''),(1,'물가 3.5 3.2 근원물가 때문에 금리 주식 영향 가능 다만'),
            (4,'고용 경기 금리 임금 물가 때문에 달러 가능 다만 단정하지 않겠다.'),(9007199254740991,'인하 주식 자산 축소 고용 4.75 5.00 0.50 불확실')]]

def golden(base):
    case=base/'domain'; baseline=json.loads((case/'baseline.json').read_text())
    node=str(Path(shutil.which('node')).resolve())
    argv=[node,'--experimental-strip-types','--input-type=module','-e',GOLDEN]
    g=Gateway(baseline['source'],case/'golden-state',{'version':'003-golden','commands':[{'argv':argv}]},actor='independent-baseline')
    result=g.submit({'tool':'shell','operation':'exec','argv':argv,'stdin':json.dumps(inputs(),ensure_ascii=False)})
    if result['exit_code']!=0: raise ValueError(str(result))
    record={'inputs':inputs(),'golden':json.loads(result['stdout']),'result':result}
    (case/'golden.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
    print('Captured 12 valid-input baseline scores/forecasts from unchanged original domain source.')

def verify(base,kind,number):
    case=base/kind; work=case/'workspace'; session=case/f'task-{number}'
    live=validate_session(session,work,case/'operator-state')
    policy=json.loads((case/'operator-state/policy.json').read_text())
    node=policy['commands'][0]['argv'][0] if kind=='domain' else None
    argv=[str(Path(sys.executable).resolve()),'-B','-c',C_CHECK] if kind=='c' else [node,'--experimental-strip-types','--input-type=module','-e',DOMAIN_CHECK]
    policy['commands'].append({'argv':argv,'write_paths':['build/test-data'] if kind=='c' else []})
    g=Gateway(work,case/f'reviewer-{number}',policy,actor='independent-reviewer')
    checks=[]
    if kind=='c':
        checks.append({'label':'release build',**g.submit(dict(tool='shell',operation='run',profile='c-build'))})
    tests=g.submit(dict(tool='shell',operation='run',profile='c-tests' if kind=='c' else 'node-tests'))
    checks.append({'label':'project tests',**tests})
    stdin=''
    if kind=='domain':
        record=json.loads((case/'golden.json').read_text()); stdin=json.dumps({'task':number,'inputs':record['inputs'],'golden':record['golden']},ensure_ascii=False)
    checks.append({'label':'independent behavior',**g.submit(dict(tool='shell',operation='exec',argv=argv,stdin=stdin))})
    if kind=='c':
        checks.append({'label':'debug build',**g.submit(dict(tool='shell',operation='run',profile='c-build',mode='debug'))})
        checks.append({'label':'debug independent behavior',**g.submit(dict(tool='shell',operation='exec',argv=argv))})
    status=g.submit(dict(tool='git',operation='status')); history=g.submit(dict(tool='git',operation='log'))
    events=read_session_events(session)
    calls=[e['item'] for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='mcp_tool_call']
    decisions=collections.Counter((c.get('result') or {}).get('structured_content',{}).get('decision','transport_error') for c in calls)
    compact=[{'tool':c['tool'],'arguments':c['arguments'],'result':(c.get('result') or {}).get('structured_content',{}),'error':c.get('error')} for c in calls]
    final=[e['item']['text'] for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
    exitcode=session_exit(session)
    passed=live['passed'] and exitcode==0 and all(c['executed'] and c['exit_code']==0 for c in checks) and status['executed'] and not status['stdout'].strip() and history['executed']
    record={'kind':kind,'task':number,'calls':compact,'tool_calls':len(calls),'decisions':dict(decisions),'checks':checks,
        'git_status':status,'git_history':history,'model_final':final[-1] if final else '',
        'session_evidence':live,'passed':passed}
    (case/f'verification-{number}.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
    print(json.dumps({k:record[k] for k in ('kind','task','tool_calls','decisions','passed')}),flush=True)
    return passed

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--root',required=True); p.add_argument('--golden',action='store_true')
    p.add_argument('--kind',choices=['c','domain']); p.add_argument('--task',type=int,choices=[1,2,3]); a=p.parse_args()
    base=Path(a.root).resolve()
    if a.golden: golden(base)
    else: raise SystemExit(0 if verify(base,a.kind,a.task) else 1)
