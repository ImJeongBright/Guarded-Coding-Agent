"""Codex PreToolUse supplemental gate. Must be enabled and trusted by the host.
It never executes agent actions. The actual authority boundary remains Gateway.
"""
import json
import sys

ALLOWED={'mcp__guard__guard_filesystem','mcp__guard__guard_shell','mcp__guard__guard_git','update_plan'}

def main():
    allowed=False
    try:
        raw=sys.stdin.read(2_000_001)
        value=json.loads(raw) if len(raw)<=2_000_000 else None
        allowed=(isinstance(value,dict) and value.get('hook_event_name')=='PreToolUse' and value.get('tool_name') in ALLOWED)
    except (ValueError,TypeError,RecursionError):
        pass
    reason='Use the guard MCP tools. Native shell/file edits and other tool routes are disabled for this guarded session.'
    output={'hookSpecificOutput':{'hookEventName':'PreToolUse','permissionDecision':'allow' if allowed else 'deny'}}
    if not allowed:
        output['hookSpecificOutput']['permissionDecisionReason']=reason
        print(reason,file=sys.stderr)
    print(json.dumps(output))
    return 0 if allowed else 2

if __name__=='__main__':
    raise SystemExit(main())
