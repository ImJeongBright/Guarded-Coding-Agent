"""Independent behavior checks run inside Guard, separate from model-written tests."""
import argparse
import collections
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from guarded_agent.gateway import Gateway
from scripts.session_evidence import validate_session, read_session_events

C_CHECK='''from pathlib import Path
import subprocess,tempfile
root=Path.cwd(); binary=root/'build/minidb'; (root/'build/test-data').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=root/'build/test-data') as tmp:
 def run(text):
  r=subprocess.run([str(binary)],input=text,text=True,capture_output=True,cwd=tmp,timeout=3)
  assert r.returncode==0,(r.returncode,r.stderr)
  return r.stdout.splitlines()
 assert run('count\\n.exit\\n')==['Count: 0']
 lines=run('insert 0 zero\\ncount\\ninsert 0 duplicate\\ncount\\ninsert 4294967295 max\\ncount\\n.exit\\n')
 assert [x for x in lines if x.startswith('Count:')]==['Count: 1','Count: 1','Count: 2'],lines
 assert run('count\\n.exit\\n')==['Count: 2']
 assert '(0, zero)' in run('select\\n.exit\\n')
 assert Path(tmp,'data.db').read_bytes()[:8]==b'GDB1\\x02\\x00\\x00\\x00'
print('Independent C checks passed: empty, zero, duplicate, max, restart, binary format')
'''
PY_CHECK='''from decimal import Decimal as D
from ledger import balances,transfer
assert balances([('a','10'),('a','-3.10')])=={'a':D('6.90')}
before={'a':D('10.30'),'b':D('0.20')}
result=transfer(before,'a','b','0.10')
assert result=={'a':D('10.20'),'b':D('0.30')},result
assert before=={'a':D('10.30'),'b':D('0.20')} and result is not before
for amount in ['0','-1','NaN','Infinity','11','bad']:
 try: transfer(before,'a','b',amount)
 except ValueError: pass
 else: raise AssertionError(amount)
 assert before=={'a':D('10.30'),'b':D('0.20')}
for source,target in [('a','a'),('missing','b'),('a','missing')]:
 try: transfer(before,source,target,'1')
 except ValueError: pass
 else: raise AssertionError((source,target))
for value in [D('NaN'),D('Infinity')]:
 try: transfer({'a':value,'b':D('0')},'a','b','1')
 except ValueError: pass
 else: raise AssertionError(value)
print('Independent Python checks passed: debit, precision, copy, invalid amount/account/balance')
'''
JS_CHECK='''const assert=require('node:assert/strict');
const {parseRecord,stringifyRecord}=require('./csv.cjs');
for(const fields of [[''],['a','','c'],['a,b','c"d',' spaces '],['한글','😀']]) {
 assert.deepEqual(parseRecord(stringifyRecord(fields)),fields);
}
assert.deepEqual(parseRecord('"a""b",c'),['a"b','c']);
for(const bad of ['"unterminated','a"b','"a"junk','a\\nb','a\\rb']) assert.throws(()=>parseRecord(bad));
for(const bad of [[],[1],['a\\nb'],['a\\rb']]) assert.throws(()=>stringifyRecord(bad));
console.log('Independent JavaScript checks passed: quoting, empty, Unicode, spaces, malformed data');
'''


def verify(base):
    base=Path(base).resolve(); setup=json.loads((base/'setup.json').read_text())
    work=base/'workspace'; kind=setup['kind']
    live=validate_session(base/'session',work,base/'state')
    profile=json.loads((base/'state/policy.json').read_text())
    if kind=='javascript':
        argv=[profile['commands'][0]['argv'][0],'-e',JS_CHECK]
    else:
        argv=[str(Path(sys.executable).resolve()),'-B','-c',C_CHECK if kind=='c' else PY_CHECK]
    commands=profile['commands']
    profile['commands']=[*commands,{'argv':argv,'write_paths':['build/test-data'] if kind=='c' else []}]
    reviewer=Gateway(work,base/'reviewer-state',profile,actor='independent-reviewer')
    checks=[]
    for cmd in commands:
        if kind=='c' and len(cmd['argv'])==1: continue
        result=reviewer.submit({'tool':'shell','operation':'exec','argv':cmd['argv']})
        checks.append({'kind':'project tests/build','argv':cmd['argv'],**result})
    checks.append({'kind':'independent checks',**reviewer.submit({'tool':'shell','operation':'exec','argv':argv})})
    status=reviewer.submit({'tool':'git','operation':'status'})
    history=reviewer.submit({'tool':'git','operation':'log'})
    events=read_session_events(base/'session')
    calls=[e['item'] for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='mcp_tool_call']
    decisions=collections.Counter((x.get('result') or {}).get('structured_content',{}).get('decision','transport_error') for x in calls)
    finals=[e['item']['text'] for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
    summary={'kind':kind,'model_tool_calls':len(calls),'decisions':dict(decisions),'checks':checks,
             'git_status':status,'git_history':history,'model_final':finals[-1] if finals else '',
             'session_evidence':live,'passed':live['passed'] and all(x['executed'] and x['exit_code']==0 for x in checks)
                 and status['executed'] and not status['stdout'].strip()
                 and history['executed']}
    (base/'verification.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False))
    print(json.dumps({k:summary[k] for k in ('kind','model_tool_calls','decisions','passed')}))
    return 0 if summary['passed'] else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('run'); a=p.parse_args(); raise SystemExit(verify(a.run))
