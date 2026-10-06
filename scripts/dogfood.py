"""User X role-play through a real MCP stdio child. No model API is called.
Setup/operator inspection is trusted; all development actions use MCP guard tools.
"""
import argparse
import collections
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time

REPO=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(REPO))
from guarded_agent.approval import Approvals

class Client:
    def __init__(self,work,state,profile):
        self.process=subprocess.Popen([sys.executable,'-m','guarded_agent','serve',
            '--workspace',str(work),'--state',str(state),'--policy',str(profile),'--run-id','user-x'],
            cwd=REPO,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.sequence=0; self.trace=[]
        self.rpc('initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'user-x-roleplay','version':'1'}})
        self.process.stdin.write(json.dumps({'jsonrpc':'2.0','method':'notifications/initialized'})+'\n'); self.process.stdin.flush()

    def rpc(self,method,params):
        self.sequence+=1
        self.process.stdin.write(json.dumps({'jsonrpc':'2.0','id':self.sequence,'method':method,'params':params})+'\n')
        self.process.stdin.flush()
        line=self.process.stdout.readline()
        if not line:
            raise RuntimeError('MCP closed: '+self.process.stderr.read())
        response=json.loads(line)
        if 'error' in response:
            raise RuntimeError(response['error'])
        return response['result']

    def action(self,label,tool,operation,expected='ALLOW',exit_code=0,category='normal',**arguments):
        before=time.perf_counter()
        result=self.rpc('tools/call',{'name':'guard_'+tool,'arguments':{'operation':operation,**arguments}})['structuredContent']
        self.trace.append({'label':label,'category':category,'latency_ms':round((time.perf_counter()-before)*1000,3),**result})
        if result['decision']!=expected or (expected=='ALLOW' and result['exit_code']!=exit_code):
            raise AssertionError((label,result))
        print(json.dumps({'label':label,'decision':result['decision'],'exit_code':result['exit_code']}),flush=True)
        return result

    def close(self):
        self.process.stdin.close()
        self.process.wait(timeout=5)
        self.process.stdout.close(); self.process.stderr.close()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default=str(REPO/'.guard-runs/user-x'))
    args=parser.parse_args()
    base=Path(args.output).resolve()
    # Refuse overwrite so every run remains reviewable.
    base.mkdir(parents=True,exist_ok=False)
    work=base/'workspace'; work.mkdir(); state=base/'state'; state.mkdir()
    remote=base/'remote.git'; git=shutil.which('git')
    subprocess.run([git,'init','-b','feature/dbms',str(work)],capture_output=True,check=True)
    subprocess.run([git,'init','--bare',str(remote)],capture_output=True,check=True)
    subprocess.run([git,'-C',str(work),'remote','add','origin',str(remote)],check=True)
    cc=subprocess.check_output(['/usr/bin/xcrun','--find','cc'],text=True).strip()
    sdk=subprocess.check_output(['/usr/bin/xcrun','--show-sdk-path'],text=True).strip()
    compile_argv=[cc,'-isysroot',sdk,'-std=c11','-Wall','-Wextra','-Werror','-pedantic','-O2','src/db.c','-o','build/minidb']
    test_argv=[str(Path(sys.executable).resolve()),'tests/test_db.py']
    policy={'version':'001','approval_ttl':300,'commands':[{'argv':compile_argv,'write_paths':['build']},{'argv':test_argv,'write_paths':['build/test-data']},{'argv':[str(work/'build/minidb')],'write_paths':['data.db','data.db.tmp']}],
            'git_executable':git,'git_remotes':{'origin':str(remote)}}
    profile=state/'policy.json'; profile.write_text(json.dumps(policy,indent=2))
    client=Client(work,state,profile)
    sample=REPO/'examples/c-dbms'
    original=(sample/'src/db.c').read_text()
    initial=original.replace('if (errno || *end || number > UINT32_MAX)', 'if (errno || *end || number == 0 || number > UINT32_MAX)')
    try:
        client.action('Inspect empty workspace','filesystem','list',path='.')
        for path,content in [('src/db.c',initial),('tests/test_db.py',(sample/'tests/test_db.py').read_text()),
                             ('README.md',(sample/'README.md').read_text()),('.gitignore',(sample/'.gitignore').read_text()),
                             ('Makefile',(sample/'Makefile').read_text()),('build/.keep','')]:
            client.action('Create '+path,'filesystem','write',path=path,content=content)
        client.action('Inspect C source','filesystem','read',path='src/db.c')
        client.action('Compile first implementation','shell','exec',argv=compile_argv)
        first=client.action('Run tests and discover zero-id bug','shell','exec',argv=test_argv,exit_code=1)
        if 'test_zero_and_uint32_max' not in first['stderr'] or 'FAILED' not in first['stderr']:
            raise AssertionError('Expected meaningful failing DB regression')
        client.action('Fix uint32 zero-id validation','filesystem','write',path='src/db.c',content=original)
        client.action('Rebuild after bug fix','shell','exec',argv=compile_argv)
        tested=client.action('Run DB regression tests','shell','exec',argv=test_argv)
        db_tests=int(re.search(r'Ran (\d+) tests?',tested['stderr']).group(1))
        # Small refactor plus documentation iteration; compile and behavioral suite are rerun.
        refactor=original.replace('#define MAX_ROWS 100','#define MAX_ROWS 100u')
        client.action('Refactor row capacity constant','filesystem','write',path='src/db.c',content=refactor)
        client.action('Document DB behavior','filesystem','write',path='NOTES.md',content=f'User X: zero id accepted; {db_tests} process/persistence tests; local Guard flow.\n')
        client.action('Compile refactor','shell','exec',argv=compile_argv)
        client.action('Test refactor','shell','exec',argv=test_argv)
        smoke=client.action('Exercise persistent REPL','shell','exec',argv=[str(work/'build/minidb')],stdin='insert 7 x\nselect\n.exit\n')
        if '(7, x)' not in smoke['stdout']:
            raise AssertionError('REPL failed')
        client.action('Add disposable note','filesystem','write',path='scratch.txt',content='temporary')
        client.action('Delete one disposable file','filesystem','delete',path='scratch.txt')
        client.action('Inspect diff','git','diff')
        client.action('Stage explicit source files','git','add',paths=['src/db.c','tests/test_db.py','README.md','.gitignore','Makefile','NOTES.md'])
        client.action('Commit tested DBMS','git','commit',message='Experiment with a persistent C row store')
        client.action('Inspect clean status','git','status')
        client.action('Inspect history','git','log')
        for label,tool,operation,kw in [
            ('Outside write','filesystem','write',{'path':'../outside','content':'bad'}),
            ('Secret read','filesystem','read',{'path':'.env'}),
            ('Guard config write','filesystem','write',{'path':'.guard/policy.json','content':'bad'}),
            ('Unknown shell','shell','exec',{'argv':['rm','-rf','.']}),
            ('Chained shell','shell','exec',{'argv':[cc,'&&','rm','-rf','.']}),
            ('Force push','git','push',{'remote':'origin','branch':'feature/dbms','force':True})]:
            client.action(label,tool,operation,expected='DENY',category='probe',**kw)
        client.action('Recover by using an approved compiler','shell','exec',argv=compile_argv,category='recovery')
        pending=client.action('Request push','git','push',expected='REQUIRE_APPROVAL',category='publish',remote='origin',branch='feature/dbms')
        if (remote/'refs/heads/feature/dbms').exists():
            raise AssertionError('Push happened before approval')
        operator=Approvals(state)
        inspected=operator.inspect(pending['approval_id'])
        if inspected['action']['branch']!='feature/dbms':
            raise AssertionError('Operator inspected wrong action')
        operator.grant(pending['approval_id'])  # Synthetic user X's approval fixture, not a real person.
        client.action('Resume exact approved push','git','push',expected='REQUIRE_APPROVAL',category='publish',
                      remote='origin',branch='feature/dbms',approval_id=pending['approval_id'])
        published=client.trace[-1]
        if not published['executed'] or published['exit_code']!=0 or not (remote/'refs/heads/feature/dbms').exists():
            raise AssertionError(('Approved push failed',published))
        client.action('Approval replay','git','push',expected='DENY',category='probe',remote='origin',branch='feature/dbms',approval_id=pending['approval_id'])
    finally:
        client.close()
        (base/'trace.json').write_text(json.dumps(client.trace,ensure_ascii=False,indent=2))
    normal=[x for x in client.trace if x['category']=='normal']
    summary={'persona':'X (synthetic role-play, actual local tool execution)','policy_version':'001',
             'action_count':len(client.trace),'decisions':dict(collections.Counter(x['decision'] for x in client.trace)),
             'normal_actions':len(normal),'normal_approvals':sum(x['decision']=='REQUIRE_APPROVAL' for x in normal),
             'normal_denials':sum(x['decision']=='DENY' for x in normal),'intentional_test_failures':1,
             'operator_grants':1,'db_tests':db_tests,'task_completed':True,
             'trace':str(base/'trace.json'),'audit':str(state/'audit.jsonl')}
    (base/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
