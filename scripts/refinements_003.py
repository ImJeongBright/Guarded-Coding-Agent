"""Recheck observed workflow misses with the final runtime, retaining before/after."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from guarded_agent.gateway import Gateway

p=argparse.ArgumentParser(); p.add_argument('--root',required=True); a=p.parse_args(); base=Path(a.root).resolve()
case=base/'c'; g=Gateway(case/'workspace',case/'refinement-state',policy_path=case/'operator-state/policy.json',actor='X-refinement-replay')
def calls(number):
    events=[json.loads(line) for line in (case/f'task-{number}/events.jsonl').read_text().splitlines()]
    return [e['item'] for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='mcp_tool_call']
before=next(c for c in calls(2) if (c.get('result') or {}).get('structured_content',{}).get('decision')=='DENY')
search=g.submit({'tool':'filesystem',**before['arguments']})
git_before=[c['result']['structured_content'] for c in calls(1) if c['tool']=='guard_git']
git_after=[c['result']['structured_content'] for c in calls(2) if c['tool']=='guard_git']
record={'empty_query':{'request':before['arguments'],'before':before['result']['structured_content'],'after':search},
        'git_diagnostics':{'before_nonempty_stderr':sum(bool(c['stderr']) for c in git_before),
                           'after_nonempty_stderr':sum(bool(c['stderr']) for c in git_after),
                           'before_sample':git_before[0]['stderr'],'after_sample':git_after[0]['stderr']},
        'security_state_truncation':{'test':'test_shell_git.ShellGitTests.test_truncated_git_state_query_stops_before_executor',
            'before':'Truncated query fixture reached executor spy: matched_rule EXEC-ERROR',
            'after':'GT-STATE, executor not called','actual_large_repository_exploit_reproduced':False},
        'edit_temp_collision':{'test':'test_workflow_003.WorkflowTests.test_edit_temp_collision_never_deletes_preexisting_file',
            'before':'Forced UUID collision caused preexisting ordinary temp-name file to be deleted during cleanup',
            'after':'O_EXCL failure preserves original target and preexisting file; cleanup starts only after successful creation'}}
assert search['decision']=='ALLOW' and search['exit_code']==0
assert record['git_diagnostics']['after_nonempty_stderr']==0
(base/'workflow-refinements.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
print('Observed empty-query retry and Git diagnostics fixed; before/after evidence retained.')
