import json
import os
from pathlib import Path
import sqlite3
import time
import uuid
from .domain import digest

class Approvals:
    """Operator methods must never be exposed as agent tools."""
    def __init__(self, state):
        self.state = Path(state)
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.state.is_symlink() or self.state.stat().st_uid != os.getuid():
            raise ValueError('State must be an owned ordinary directory.')
        os.chmod(self.state, 0o700)
        self.db = self.state / 'approvals.sqlite3'
        if self.db.is_symlink() or (self.db.exists() and self.db.stat().st_nlink != 1):
            raise ValueError('State database must be an ordinary single-link file.')
        with self.connect() as connection:
            connection.execute('CREATE TABLE IF NOT EXISTS approvals (id TEXT PRIMARY KEY, binding TEXT NOT NULL, action TEXT NOT NULL, expires REAL NOT NULL, granted INTEGER NOT NULL DEFAULT 0, used INTEGER NOT NULL DEFAULT 0)')
        os.chmod(self.db, 0o600)

    def connect(self):
        return sqlite3.connect(self.db, timeout=10)

    def pending(self, binding, public_action, ttl):
        approval_id = uuid.uuid4().hex
        with self.connect() as c:
            c.execute('INSERT INTO approvals(id,binding,action,expires) VALUES (?,?,?,?)',
                      (approval_id, digest(binding), json.dumps(public_action), time.time()+ttl))
        return approval_id

    def inspect(self, approval_id):
        with self.connect() as c:
            row = c.execute('SELECT action,expires,granted,used FROM approvals WHERE id=?', (approval_id,)).fetchone()
        if not row:
            raise ValueError('Approval does not exist.')
        return {'action':json.loads(row[0]), 'expires':row[1], 'granted':bool(row[2]), 'used':bool(row[3])}

    def grant(self, approval_id):
        with self.connect() as c:
            result = c.execute('UPDATE approvals SET granted=1 WHERE id=? AND expires>? AND used=0 AND granted=0', (approval_id,time.time()))
            if result.rowcount != 1:
                raise ValueError('Approval expired, already granted or already consumed.')

    def consume(self, approval_id, binding):
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            result = c.execute('UPDATE approvals SET used=1 WHERE id=? AND binding=? AND granted=1 AND used=0 AND expires>?',
                               (approval_id,digest(binding),time.time()))
            return result.rowcount == 1
