"""Retain discovery, operator-reviewed registration, and identical baseline replay."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from guarded_agent.gateway import Gateway
from guarded_agent.profiles import discover, apply_candidates

parser=argparse.ArgumentParser(); parser.add_argument('--root',required=True)
parser.add_argument('--phase',choices=['discover','apply'],required=True)
args=parser.parse_args()
base=Path(args.root).resolve()
for kind in ('c','domain'):
    case=base/kind; work=case/'workspace'; state=case/'operator-state'
    record_path=case/'setup.json'
    started=time.perf_counter()
    if args.phase=='discover':
        candidate=discover(work,state)
        record={'discovery_seconds':time.perf_counter()-started,'review_started_at':time.time(),
                'candidate':candidate}
        record_path.write_text(json.dumps(record,ensure_ascii=False,indent=2))
        print(json.dumps({'kind':kind,'candidate':candidate},ensure_ascii=False),flush=True)
    else:
        record=json.loads(record_path.read_text()); candidate=record['candidate']
        ids=[c['id'] for c in candidate['commands']]
        apply_candidates(work,state,candidate['digest'],ids)
        record['apply_seconds']=time.perf_counter()-started
        record['agent_operator_review_elapsed_seconds']=time.time()-record['review_started_at']
        record['human_operator_review_measured']=False
        g=Gateway(work,state,policy_path=state/'policy.json',actor='X-replay')
        baseline=json.loads((case/'baseline.json').read_text())
        replay=[{'request':probe['request'],'result':g.submit(probe['request'])} for probe in baseline['baseline_requests']]
        record['same_request_replay']=replay
        (case/'setup.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
        print(json.dumps({'kind':kind,'registered_ids':ids,'replay_allowed':sum(p['result']['decision']=='ALLOW' for p in replay),
            'replay_total':len(replay),'replay_errors':[p['result'] for p in replay if p['result']['exit_code']!=0]}),flush=True)
