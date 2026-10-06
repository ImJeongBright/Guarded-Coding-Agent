import json
import os
import re
import time
import stat
import uuid
from pathlib import Path

# Best effort result redaction is additional to denying access to secret files.
_PATTERNS = [
    (re.compile(r'(?i)\b(?:token|password|secret|api[_-]?key)\s*[=:]\s*[^\s,;"\']+'), '[REDACTED]'),
    (re.compile(r'\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{8,}|AKIA[A-Z0-9]{16})\b'), '[REDACTED]'),
    (re.compile(r'(?i)Bearer\s+[^\s"\']+'), 'Bearer [REDACTED]'),
    (re.compile(r'-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----', re.S), '[REDACTED KEY]'),
]

def redact(value):
    if isinstance(value, dict):
        return {k: ('[OMITTED]' if k in ('content','stdin','old_text','new_text') else redact(v)) for k,v in value.items()}
    if isinstance(value, list):
        return [redact(x) for x in value]
    if isinstance(value, str):
        for pattern, replacement in _PATTERNS:
            value = pattern.sub(replacement, value)
        return value
    return value

class Audit:
    def __init__(self, path):
        self.path = Path(path)

    def record(self, event):
        event_id = uuid.uuid4().hex
        safe = redact({'event_id':event_id, 'timestamp':time.time(), **event})
        # Output content is returned to the caller, but not persisted in the audit.
        if 'result' in safe:
            result = safe['result']
            safe['result'] = {k:v for k,v in result.items() if k not in ('stdout','stderr','matches')}
        line = json.dumps(safe, ensure_ascii=False, sort_keys=True).encode() + b'\n'
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            info=os.fstat(fd)
            if info.st_nlink != 1 or not stat.S_ISREG(info.st_mode):
                raise OSError('Audit must be an ordinary single-link file.')
            remaining=memoryview(line)
            while remaining:
                written=os.write(fd,remaining)
                if not written:
                    raise OSError('Audit write did not make progress.')
                remaining=remaining[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        return event_id
