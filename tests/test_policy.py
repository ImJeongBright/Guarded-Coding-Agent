import unittest
from guarded_agent.domain import Action, Decision
from guarded_agent.policy import evaluate

class PolicyTests(unittest.TestCase):
    def test_local_action_is_allowed(self):
        self.assertEqual(evaluate(Action('filesystem','write',{'path':'src/a.c'})).decision,Decision.ALLOW)

    def test_sensitive_and_scope_deny_override_local_allow(self):
        for path in ['.env','../a','/outside','.GIT/config']:
            self.assertEqual(evaluate(Action('filesystem','write',{'path':path})).decision,Decision.DENY)

    def test_remote_approval_overrides_git_allow(self):
        self.assertEqual(evaluate(Action('git','push',{'force':False,'branch':'feature/a'})).decision,Decision.APPROVAL)

    def test_force_and_protected_branch_override_approval(self):
        for data in [{'force':True,'branch':'feature/a'},{'force':False,'branch':'main'}]:
            self.assertEqual(evaluate(Action('git','push',data)).decision,Decision.DENY)

    def test_unknown_action_denied(self):
        self.assertEqual(evaluate(Action('shell','eval',{})).decision,Decision.DENY)

if __name__=='__main__':
    unittest.main()
