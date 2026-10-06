from dataclasses import dataclass
from enum import Enum
import hashlib
import json

MAX_CONTENT = 1_000_000
MAX_OUTPUT = 64_000
# Internal Git path metadata never leaves the executor; keep it separate from
# bounded user-visible output while still failing closed on excessive state.
MAX_GIT_METADATA_OUTPUT = 8 * 1024 * 1024
MAX_GIT_PATHS = 250_000

class Decision(str, Enum):
    ALLOW = 'ALLOW'
    APPROVAL = 'REQUIRE_APPROVAL'
    DENY = 'DENY'

@dataclass(frozen=True)
class Verdict:
    decision: Decision
    rule: str
    reason: str

@dataclass(frozen=True)
class Action:
    tool: str
    operation: str
    data: dict

    def payload(self):
        return {'tool': self.tool, 'operation': self.operation, **self.data}

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest()

def decide(matches):
    rank = {Decision.ALLOW: 0, Decision.APPROVAL: 1, Decision.DENY: 2}
    return max(matches, key=lambda x: rank[x.decision]) if matches else Verdict(
        Decision.DENY, 'CORE-UNKNOWN', 'No explicit capability matches this action.')

SCHEMA = {
    ('filesystem','read'): ({'path'}, {'start_line','end_line'}),
    ('filesystem','list'): ({'path'}, set()),
    ('filesystem','search'): ({'path','query'}, {'glob','exclude_dirs'}),
    ('filesystem','edit'): ({'path','old_text','new_text','expected_sha256'}, set()),
    ('filesystem','write'): ({'path','content'}, set()),
    ('filesystem','delete'): ({'path'}, set()),
    ('shell','exec'): ({'argv'}, {'cwd','stdin'}),
    ('shell','run'): ({'profile'}, {'mode','filter','stdin'}),
    ('git','status'): (set(), set()),
    ('git','diff'): (set(), {'paths','staged'}),
    ('git','log'): (set(), set()),
    ('git','add'): ({'paths'}, set()),
    ('git','commit'): ({'message'}, set()),
    ('git','branch'): ({'name'}, set()),
    ('git','push'): ({'remote','branch'}, {'force'}),
}

def validate(request):
    if not isinstance(request, dict):
        raise ValueError('Request must be an object.')
    tool, operation = request.get('tool'), request.get('operation')
    if not isinstance(tool, str) or not isinstance(operation, str):
        raise ValueError('tool and operation must be strings.')
    schema = SCHEMA.get((tool, operation))
    if schema is None:
        raise ValueError('Unknown tool or operation.')
    required, optional = schema
    if not required <= request.keys() or not request.keys() <= required | optional | {'tool','operation'}:
        raise ValueError('Missing or unexpected fields.')
    for key, value in request.items():
        if key in ('argv','paths','exclude_dirs'):
            maximum = 32 if key == 'exclude_dirs' else 128
            minimum = 0 if key == 'exclude_dirs' else 1
            if not isinstance(value, list) or not minimum <= len(value) <= maximum:
                raise ValueError('Expected a bounded string array.')
            if any(not isinstance(x, str) or not x or '\0' in x or len(x)>4096 for x in value):
                raise ValueError('Invalid array element.')
        elif key in ('force','staged'):
            if type(value) is not bool:
                raise ValueError(key+' must be boolean.')
        elif key in ('start_line','end_line'):
            if type(value) is not int or not 1 <= value <= 1_000_000:
                raise ValueError('Line numbers must be positive bounded integers.')
        elif not isinstance(value, str) or '\0' in value or len(value.encode()) > (
                MAX_CONTENT if key in ('content','stdin','old_text','new_text') else 4096):
            raise ValueError('Invalid or oversized string.')
    return {key:list(value) if isinstance(value,list) else value for key,value in request.items()}
