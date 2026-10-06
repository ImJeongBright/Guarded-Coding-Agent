import json
from pathlib import Path
import subprocess
import sys
import unittest

HOOK=Path(__file__).resolve().parent.parent/'scripts/codex_pre_tool.py'

class HostHookTests(unittest.TestCase):
    def invoke(self,value):
        data=json.dumps(value) if not isinstance(value,str) else value
        result=subprocess.run([sys.executable,str(HOOK)],input=data,text=True,capture_output=True)
        return result,json.loads(result.stdout)

    def test_native_shell_patch_and_unknown_denied(self):
        for name in ['Bash','exec_command','apply_patch','write_stdin','mcp__other__guard_filesystem','unknown']:
            result,response=self.invoke({'hook_event_name':'PreToolUse','tool_name':name,'tool_input':{}})
            self.assertEqual(result.returncode,2)
            self.assertEqual(response['hookSpecificOutput']['permissionDecision'],'deny')

    def test_only_exact_guard_tools_and_safe_plan_allowed(self):
        for name in ['mcp__guard__guard_filesystem','mcp__guard__guard_shell','mcp__guard__guard_git','update_plan']:
            result,response=self.invoke({'hook_event_name':'PreToolUse','tool_name':name,'tool_input':{}})
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(response['hookSpecificOutput']['permissionDecision'],'allow')

    def test_malformed_hook_input_denied(self):
        for value in ['not JSON',[],{}, {'hook_event_name':'PostToolUse','tool_name':'mcp__guard__guard_shell'}]:
            result,response=self.invoke(value)
            self.assertEqual(result.returncode,2)
            self.assertEqual(response['hookSpecificOutput']['permissionDecision'],'deny')

if __name__=='__main__':
    unittest.main()
