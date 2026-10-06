"""Bind a live session to its starting revision, Guard audit, and new commits.

These are operator-side evidence checks, not an assertion of task correctness.
The workload verifiers still run independent behavior checks through Guard.
Evidence recorded before this format existed is deliberately not inferred.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid

from guarded_agent.gateway import Gateway
from guarded_agent.audit import redact
from guarded_agent.domain import validate

MAX_EVIDENCE_BYTES = 32 * 1024 * 1024
OID = re.compile(r'^[0-9a-f]{40}(?:[0-9a-f]{24})?$')
COMMIT_OUTPUT = re.compile(r'^\[[^\]\n]* ([0-9a-f]{7,64})\]', re.M)
TOOLS = {'guard_filesystem': 'filesystem', 'guard_shell': 'shell', 'guard_git': 'git'}


def _bytes(path, *, missing=False):
    path = Path(path)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        if missing:
            return b''
        raise
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_EVIDENCE_BYTES:
            raise ValueError('Evidence must be a bounded ordinary single-link file: '+path.name)
        with os.fdopen(os.dup(fd), 'rb') as stream:
            data = stream.read(MAX_EVIDENCE_BYTES+1)
        if len(data) > MAX_EVIDENCE_BYTES:
            raise ValueError('Evidence exceeded its byte limit: '+path.name)
        return data
    finally:
        os.close(fd)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _digest(record):
    return _sha(json.dumps(record, sort_keys=True, separators=(',', ':')).encode())


def _save(path, record):
    Path(path).write_text(json.dumps(record, indent=2, ensure_ascii=False)+'\n')


def _audit_cursor(state):
    data = _bytes(Path(state)/'audit.jsonl', missing=True)
    if data and not data.endswith(b'\n'):
        raise ValueError('Audit has an incomplete record.')
    return {'bytes': len(data), 'sha256': _sha(data)}


def read_session_events(session):
    try:
        rows = [json.loads(line) for line in _bytes(Path(session)/'events.jsonl').splitlines()]
        return rows if all(isinstance(row, dict) for row in rows) else []
    except (OSError, ValueError):
        return []


def session_exit(session):
    try:
        return json.loads(_bytes(Path(session)/'exit.json')).get('exit_code')
    except (OSError, ValueError, AttributeError):
        return None


def _repository(gateway, start=None):
    gateway._check_links()
    gateway.git._config_check()
    head = gateway.git._query('rev-parse', '--verify', 'HEAD')
    if not OID.fullmatch(head):
        raise ValueError('Expected a full starting Git revision.')
    status = gateway.git._query('status', '--porcelain=v1', '-z')
    record = {'head': head, 'clean': not status, 'status': status,
              'workspace': str(gateway.workspace), 'workspace_identity': list(gateway.fs.identity),
              'policy_digest': gateway.policy_digest}
    if start is not None:
        commits = gateway.git._query('rev-list', '--max-count=101', start+'..'+head).splitlines()
        if len(commits) > 100 or any(not OID.fullmatch(oid) for oid in commits):
            raise ValueError('New commit range cannot be validated within its bound.')
        # A reset to an unrelated/preexisting revision cannot count as new work.
        gateway.git._query('merge-base', '--is-ancestor', start, head)
        changed = {}
        for oid in commits:
            paths = gateway.git._state_paths('diff-tree', '--no-commit-id', '--name-only', '-r', '-z', oid)
            changed[oid] = paths
        record.update(new_commits=commits, changed_paths=changed)
    return record


def start_session(workspace, state, output):
    """Run before model launch; reject dirty inputs instead of inheriting work."""
    gateway = Gateway(workspace, state, policy_path=Path(state)/'policy.json', actor='session-recorder')
    repository = _repository(gateway)
    if not repository['clean']:
        raise ValueError('Live workload evidence requires a clean starting checkout.')
    record = {'format': 1, 'session_id': uuid.uuid4().hex, 'started_at': time.time(),
              'state': str(Path(state).resolve()), **repository, 'audit': _audit_cursor(state)}
    _save(Path(output)/'session-baseline.json', record)
    return record


def finish_session(workspace, state, output, baseline, exit_code):
    """Freeze model events and ending repository/audit before independent review."""
    output = Path(output)
    gateway = Gateway(workspace, state, policy_path=Path(state)/'policy.json', actor='session-recorder')
    record = {'format': 1, 'session_id': baseline['session_id'], 'baseline_sha256': _digest(baseline),
              'finished_at': time.time(), 'exit_code': exit_code,
              **_repository(gateway, baseline['head']), 'audit': _audit_cursor(state),
              'events_sha256': _sha(_bytes(output/'events.jsonl')),
              'exit_sha256': _sha(_bytes(output/'exit.json'))}
    _save(output/'session-completion.json', record)
    return record


def _historical_action(gateway, request, recorded):
    """Check call arguments without reinterpreting a past Git index/diff.

    A committed deletion is no longer in the current index, and a staged diff
    is empty after commit. Those current facts must not invalidate the original
    action. The audit provides the then-validated source set; only its shape and
    scope are checked again, while caller-controlled arguments match exactly.
    """
    tool, operation = request['tool'], request['operation']
    if tool != 'git':
        adapter = gateway.fs if tool == 'filesystem' else gateway.shell
        return redact(adapter.normalize(request).payload())
    data = {}
    if operation == 'status':
        data['args'] = ['status', '--short']
    elif operation == 'log':
        data['args'] = ['log', '-10', '--oneline']
    elif operation in ('add', 'diff'):
        paths = [gateway.fs.relative(path) for path in request.get('paths', [])]
        if any(path == '.' for path in paths):
            raise ValueError('Historical Git paths must name explicit files.')
        options = ['--no-ext-diff', '--no-textconv', '--no-renames'] if operation == 'diff' else []
        if operation == 'diff' and request.get('staged', False):
            options.insert(0, '--cached')
        data['args'] = [operation, *options, '--', *paths]
        if operation == 'diff':
            sources = recorded.get('source_paths')
            if not isinstance(sources, list) or any(not isinstance(path, str) or gateway.fs.relative(path) != path for path in sources):
                raise ValueError('Historical Git diff has an invalid source set.')
            data['source_paths'] = sources
    elif operation == 'commit':
        if not request['message'].strip():
            raise ValueError('Historical commit message is empty.')
        data['args'] = ['commit', '-m', request['message']]
    elif operation == 'branch':
        gateway.git._branch(request['name'])
        data['args'] = ['checkout', '-b', request['name']]
    else:
        raise ValueError('Live workload evidence accepts only local Git operations.')
    return redact({'tool':tool, 'operation':operation, **data})


def validate_session(session, workspace, state):
    """Return attributable live work, failing closed on missing or failed evidence."""
    session, workspace, state = Path(session), Path(workspace).resolve(), Path(state).resolve()
    errors, calls, commits = [], [], []
    report = {'passed': False, 'errors': errors, 'tool_calls': 0, 'new_commits': commits}
    try:
        baseline = json.loads(_bytes(session/'session-baseline.json'))
        completion = json.loads(_bytes(session/'session-completion.json'))
        if baseline['format'] != 1 or completion['format'] != 1:
            raise ValueError('Unknown session evidence format.')
        if completion['session_id'] != baseline['session_id'] or completion['baseline_sha256'] != _digest(baseline):
            raise ValueError('Session completion does not bind its starting evidence.')
        if baseline['workspace'] != str(workspace) or baseline['state'] != str(state):
            raise ValueError('Session evidence belongs to a different workspace/state.')
        for key in ('workspace', 'workspace_identity', 'policy_digest'):
            if completion[key] != baseline[key]:
                raise ValueError('Session '+key+' changed.')
        if not baseline['clean'] or not completion['clean']:
            errors.append('Starting and ending checkouts must both be clean.')
        gateway = Gateway(workspace, state, policy_path=state/'policy.json', actor='session-reviewer')
        events_bytes = _bytes(session/'events.jsonl')
        exit_bytes = _bytes(session/'exit.json')
        if _sha(events_bytes) != completion['events_sha256'] or _sha(exit_bytes) != completion['exit_sha256']:
            raise ValueError('Session events or CLI exit evidence changed after capture.')
        if json.loads(exit_bytes)['exit_code'] != 0 or completion['exit_code'] != 0:
            errors.append('CLI did not exit successfully.')
        events = [json.loads(line) for line in events_bytes.splitlines()]
        completed = [event for event in events if event.get('type') == 'turn.completed']
        if (not completed or any(event.get('type') in ('turn.failed', 'error') for event in events)
            or sum(event.get('type') == 'turn.started' for event in events) != len(completed)):
            errors.append('Model turn did not complete successfully.')
        calls = [event['item'] for event in events if event.get('type') == 'item.completed'
                 and event.get('item', {}).get('type') == 'mcp_tool_call']
        report['tool_calls'] = len(calls)
        if not calls:
            errors.append('No Guard tool calls were completed.')
        if any(event.get('type') == 'item.completed' and event.get('item', {}).get('type') in
               ('command_execution', 'file_change', 'web_search', 'collab_tool_call') for event in events):
            errors.append('Session used native tool capabilities outside Guard.')
        audit = _bytes(state/'audit.jsonl', missing=True)
        before, after = baseline['audit'], completion['audit']
        if not 0 <= before['bytes'] <= after['bytes'] <= len(audit):
            raise ValueError('Session audit cursor is invalid.')
        if _sha(audit[:before['bytes']]) != before['sha256'] or _sha(audit[:after['bytes']]) != after['sha256']:
            raise ValueError('Session audit prefix was changed or truncated.')
        window = [json.loads(line) for line in audit[before['bytes']:after['bytes']].splitlines()]
        decisions = {event['event_id']: event for event in window if event.get('phase') == 'decision'}
        results = {event['parent']: event for event in window if event.get('phase') == 'result'}
        if (len(decisions) != sum(event.get('phase') == 'decision' for event in window)
            or len(results) != sum(event.get('phase') == 'result' for event in window)):
            raise ValueError('Session audit contains duplicate decision/result identities.')
        used, successful, commit_prefixes = set(), set(), []
        for call in calls:
            tool = TOOLS.get(call.get('tool'))
            result = (call.get('result') or {}).get('structured_content')
            # Codex marks a returned MCP isError (for example, a red test) as
            # "failed" even when transport and Guard audit both succeeded.
            # A bounded, audited failure can be followed by a successful fix.
            if (call.get('server') != 'guard' or tool is None or call.get('status') not in ('completed', 'failed')
                or call.get('error') or not isinstance(result, dict)):
                errors.append('Guard transport/tool call failed or used another server.')
                continue
            event_id = result.get('audit_event_id')
            decision = decisions.get(event_id)
            if decision is None or event_id in used:
                errors.append('Guard call has no unique decision audit in this session.')
                continue
            used.add(event_id)
            arguments = call.get('arguments')
            if not isinstance(arguments, dict):
                errors.append('Guard call arguments are invalid.')
                continue
            operation = arguments.get('operation')
            action = decision.get('action', {})
            try:
                if 'tool' in arguments:
                    raise ValueError('MCP arguments cannot override their tool.')
                request = validate({**{key: value for key, value in arguments.items() if key != 'approval_id'}, 'tool': tool})
                if action == {'invalid':True} and decision.get('decision') == 'DENY' and result.get('decision') == 'DENY' and result.get('executed') is False:
                    # Invalid requests intentionally omit their raw content in
                    # audit. They cannot satisfy any required execution/effect.
                    expected_action = action
                else:
                    expected_action = _historical_action(gateway, request, action)
            except ValueError:
                expected_action = {'invalid': True}
            if (decision.get('run_id') != result.get('run_id') or decision.get('actor') != 'coding-agent'
                or action != expected_action
                or decision.get('approval_id') != arguments.get('approval_id')
                or decision.get('policy_digest') != baseline['policy_digest']):
                errors.append('Guard call identity/action does not match its session audit.')
                continue
            if result.get('audit_error'):
                errors.append('Guard execution audit was not persisted.')
            audited_result = results.get(event_id, {}).get('result')
            if result.get('executed') or audited_result is not None:
                if not isinstance(audited_result, dict) or any(audited_result.get(key) != result.get(key) for key in
                        ('decision', 'executed', 'exit_code', 'run_id', 'matched_rule', 'audit_event_id')):
                    errors.append('Guard execution result differs from its audit.')
                    continue
            if result.get('executed') and result.get('exit_code') == 0:
                successful.add((tool, operation))
                if tool == 'git' and operation == 'commit':
                    match = COMMIT_OUTPUT.search(result.get('stdout', ''))
                    if not match:
                        errors.append('Successful commit lacks its resulting revision.')
                    else:
                        commit_prefixes.append(match.group(1))
        if used != set(decisions):
            errors.append('Session contains Guard decisions without corresponding model calls.')
        for kind, alternatives in [('filesystem mutation', {('filesystem', op) for op in ('write', 'edit', 'delete')}),
                                   ('successful shell check', {('shell', 'exec'), ('shell', 'run')}),
                                   ('explicit staging', {('git', 'add')}), ('local commit', {('git', 'commit')})]:
            if not successful.intersection(alternatives):
                errors.append('Session lacks '+kind+'.')
        current = _repository(gateway, baseline['head'])
        for key in ('head', 'clean', 'workspace_identity', 'policy_digest', 'new_commits', 'changed_paths'):
            if current[key] != completion[key]:
                errors.append('Repository no longer matches the captured session '+key+'.')
        commits.extend(completion['new_commits'])
        if not commits or baseline['head'] == completion['head']:
            errors.append('Session introduced no new reachable commit.')
        matched = []
        for prefix in commit_prefixes:
            candidates = [oid for oid in commits if oid.startswith(prefix)]
            if len(candidates) != 1:
                errors.append('Commit response does not identify a new session revision.')
            else:
                matched.append(candidates[0])
        if len(matched) != len(set(matched)) or set(matched) != set(commits):
            errors.append('New commits are not exactly attributable to successful Guard commit calls.')
        if any(not completion['changed_paths'].get(oid) for oid in commits):
            errors.append('Session commit contains no file change.')
        report.update(start_head=baseline['head'], end_head=completion['head'], session_id=baseline['session_id'])
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        errors.append('Session evidence unavailable or invalid: '+str(error))
    report['passed'] = not errors
    return report
