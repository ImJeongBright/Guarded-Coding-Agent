import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from .approval import Approvals
from .audit import redact
from .gateway import Gateway
from .mcp import Server

def main():
    parser=argparse.ArgumentParser(description='Local deterministic coding-agent tool gateway')
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('init','exec','serve'):
        command=sub.add_parser(name)
        command.add_argument('--workspace',required=True)
        command.add_argument('--state',required=True)
        if name=='init':
            command.add_argument('--c-dbms',action='store_true',help='Create narrow compiler/test profiles for the C DBMS example')
        else:
            command.add_argument('--policy')
            command.add_argument('--run-id')
    approve=sub.add_parser('approve',help='Operator-only: inspect and grant an exact pending action')
    approve.add_argument('--state',required=True)
    approve.add_argument('approval_id')
    inspect=sub.add_parser('inspect')
    inspect.add_argument('--state',required=True)
    inspect.add_argument('approval_id')
    for name in ('discover','profile-apply'):
        command=sub.add_parser(name,help='Operator-only profile discovery/review; never exposed as an agent tool')
        command.add_argument('--workspace',required=True)
        command.add_argument('--state',required=True)
        if name=='profile-apply':
            command.add_argument('--reviewed-digest',required=True)
            command.add_argument('--ids',nargs='+',required=True)
    args=parser.parse_args()
    try:
        if args.command in ('discover','profile-apply'):
            from .profiles import discover, apply_candidates
            value = discover(args.workspace,args.state) if args.command=='discover' else apply_candidates(args.workspace,args.state,args.reviewed_digest,args.ids)
            print(json.dumps(redact(value),ensure_ascii=False,indent=2))
            return 0
        if args.command in ('approve','inspect'):
            store=Approvals(args.state)
            pending=store.inspect(args.approval_id)
            print(json.dumps(redact(pending),ensure_ascii=False,indent=2))
            if args.command=='approve':
                if not sys.stdin.isatty():
                    parser.error('Approval requires an operator terminal; no noninteractive auto-approve option exists.')
                response=input('Grant this exact one-use action? Type approve: ')
                if response!='approve':
                    print('Not granted.'); return 1
                store.grant(args.approval_id)
                print('Granted. Resume the same request in the same run with this approval_id.')
            return 0
        if args.command=='init':
            work=Path(args.workspace).resolve(strict=True)
            state=Path(args.state).resolve()
            if state==work or work in state.parents:
                parser.error('State must be outside the workspace.')
            Approvals(state)
            policy={'version':'001','approval_ttl':300,'git_executable':shutil.which('git') or '/usr/bin/git','git_remotes':{},'commands':[]}
            if args.c_dbms:
                cc=subprocess.check_output(['/usr/bin/xcrun','--find','cc'],text=True).strip()
                sdk=subprocess.check_output(['/usr/bin/xcrun','--show-sdk-path'],text=True).strip()
                policy['commands']=[{'argv':[cc,'-isysroot',sdk,'-std=c11','-Wall','-Wextra','-Werror','-pedantic','-O2','src/db.c','-o','build/minidb'],'write_paths':['build']},
                                    {'argv':[str(work/'build/minidb')],'write_paths':['data.db','data.db.tmp']},
                                    {'argv':[str(Path(sys.executable).resolve()),'tests/test_db.py'],'write_paths':['build/test-data']}]
            target=state/'policy.json'
            fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'w') as stream:
                json.dump(policy,stream,ensure_ascii=False,indent=2)
            print(json.dumps({'policy':str(target),'workspace':str(work)}))
            return 0
        policy=args.policy or str(Path(args.state)/'policy.json')
        g=Gateway(args.workspace,args.state,policy_path=policy,run_id=args.run_id)
        if args.command=='serve':
            Server(g).serve(sys.stdin,sys.stdout)
            return 0
        data=json.loads(sys.stdin.read(2_000_001))
        if isinstance(data,dict) and 'request' in data:
            result=g.submit(data['request'],approval_id=data.get('approval_id'))
        else:
            result=g.submit(data)
        print(json.dumps(result,ensure_ascii=False))
        return 0 if result['decision']!='DENY' and result['exit_code'] in (None,0) else 1
    except (ValueError,OSError,KeyError) as error:
        print(redact(str(error)),file=sys.stderr)
        return 2
