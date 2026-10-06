import unittest
from guarded_agent.domain import Action, Decision, Verdict, decide, digest, validate

class CoreTests(unittest.TestCase):
    def test_unknown_tool_fails_closed(self):
        with self.assertRaises(ValueError):
            validate({'tool': 'browser', 'operation': 'open'})

    def test_strict_schema(self):
        for request in [None, {'tool':'filesystem','operation':'read','path':'a','extra':1},
                        {'tool':'filesystem','operation':'write','path':'a','content':7}]:
            with self.subTest(request=request), self.assertRaises(ValueError):
                validate(request)

    def test_deny_then_approval_then_allow_precedence(self):
        allow = Verdict(Decision.ALLOW, 'allow', 'ok')
        approval = Verdict(Decision.APPROVAL, 'approval', 'review')
        deny = Verdict(Decision.DENY, 'deny', 'no')
        self.assertEqual(decide([allow, approval, deny]), deny)
        self.assertEqual(decide([allow, approval]), approval)
        self.assertEqual(decide([]).decision, Decision.DENY)

    def test_digest_deterministic_and_argument_bound(self):
        self.assertEqual(digest({'a':1,'b':2}), digest({'b':2,'a':1}))
        self.assertNotEqual(digest({'path':'a'}), digest({'path':'b'}))

    def test_unknown_operation(self):
        with self.assertRaises(ValueError):
            validate({'tool':'filesystem','operation':'recursive_delete','path':'.'})

if __name__ == '__main__':
    unittest.main()
