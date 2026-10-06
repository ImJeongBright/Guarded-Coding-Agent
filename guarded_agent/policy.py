"""Pure policy evaluation; accepts only the normalizer's Action contract."""
from pathlib import PurePath
from .domain import Decision, Verdict, SCHEMA, decide
from .filesystem import Blocked, classify_parts

def evaluate(action):
    matches=[]
    if (action.tool,action.operation) not in SCHEMA:
        return decide(matches)
    matches.append(Verdict(Decision.ALLOW,
        'FS-LOCAL' if action.tool=='filesystem' else 'SH-PROFILE' if action.tool=='shell' else 'GT-LOCAL',
        'Bounded local capability allowed.'))
    if action.tool=='filesystem':
        path=PurePath(action.data['path'])
        if path.is_absolute() or '..' in path.parts:
            matches.append(Verdict(Decision.DENY,'FS-SCOPE','Normalized path must remain inside the workspace.'))
        try:
            classify_parts(path.parts)
        except Blocked as error:
            matches.append(Verdict(Decision.DENY,error.rule,str(error)))
    if action.tool=='git' and action.operation=='push':
        matches.append(Verdict(Decision.APPROVAL,'GT-PUSH','Remote state changes require approval.'))
        if action.data.get('force') or action.data.get('branch') in ('main','master'):
            matches.append(Verdict(Decision.DENY,'GT-DESTRUCTIVE','Destructive or protected branch push is unavailable.'))
    return decide(matches)
