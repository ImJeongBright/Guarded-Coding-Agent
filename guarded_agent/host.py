"""Codex 0.160 host profile. Guard remains a local, model-independent server."""
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import os
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
DISABLED_FEATURES = ('shell_tool', 'unified_exec', 'multi_agent', 'multi_agent_v2',
                     'apps', 'plugins', 'browser_use', 'browser_use_external',
                     'computer_use', 'in_app_browser', 'image_generation',
                     'code_mode', 'code_mode_only', 'view_image',
                     'shell_snapshot', 'skill_mcp_dependency_install', 'tool_suggest')


def configuration(workspace, state):
    work = Path(workspace).resolve(strict=True)
    state = Path(state).resolve(strict=True)
    if work == state or work in state.parents:
        raise ValueError('Host state must be outside the agent workspace.')
    return {
        'approval_policy': 'never',
        'sandbox_mode': 'read-only',
        'web_search': 'disabled',
        'features': {'hooks': True, **{name: False for name in DISABLED_FEATURES}},
        'log_dir': str(state/'host-logs'),
        'sqlite_home': str(state/'host-db'),
        'history': {'persistence': 'none'},
        'mcp_servers': {'guard': {
            'command': sys.executable,
            'args': [str(ROOT/'scripts/guard_stdio.py'), 'serve', '--workspace', str(work),
                     '--state', str(state), '--policy', str(state/'policy.json')],
            'required': True,
            'enabled_tools': ['guard_filesystem', 'guard_shell', 'guard_git'],
            'default_tools_approval_mode': 'approve',
            'tool_timeout_sec': 130,
        }},
        'hooks': {'PreToolUse': [{'matcher': '.*', 'hooks': [{
            'type': 'command',
            'command': shlex.join([sys.executable, str(ROOT/'scripts/codex_pre_tool.py')]),
            'timeout': 5,
        }]}]},
    }


def toml_value(value):
    if isinstance(value, dict):
        return '{'+', '.join(json.dumps(k)+' = '+toml_value(v) for k, v in value.items())+'}'
    if isinstance(value, list):
        return '['+', '.join(toml_value(v) for v in value)+']'
    return json.dumps(value, ensure_ascii=False)


def codex_version():
    binary=shutil.which('codex')
    return subprocess.run([binary, '--version'],text=True,capture_output=True,timeout=5).stdout.strip() if binary else 'unavailable'


def preflight(workspace, state):
    """Check known local hook and Gateway before launching a reviewed host session."""
    from .gateway import Gateway
    config = configuration(workspace, state)
    # Project config may merge new tools or hooks into the host. This narrow
    # launcher accepts ordinary repositories without additional project config.
    work=Path(workspace).resolve(strict=True)
    for directory in (work, *work.parents):
        if (directory/'.codex/config.toml').exists():
            if directory == Path.home():
                continue  # --ignore-user-config excludes this user layer.
            raise ValueError('Project .codex/config.toml needs separate host review; use a clean dedicated checkout.')
        if (directory/'.git').exists():
            break
    Gateway(workspace, state, policy_path=Path(state)/'policy.json')
    hook = ROOT/'scripts/codex_pre_tool.py'
    if hook.is_symlink() or not hook.is_file():
        raise ValueError('Expected a regular local Guard hook.')
    for name, decision, code in [('apply_patch', 'deny', 2),
                                  ('Bash', 'deny', 2),
                                  ('mcp__guard__guard_filesystem', 'allow', 0)]:
        result = subprocess.run([sys.executable, str(hook)], input=json.dumps({
            'hook_event_name': 'PreToolUse', 'tool_name': name, 'tool_input': {}}),
            text=True, capture_output=True, timeout=5)
        response = json.loads(result.stdout)
        if result.returncode != code or response.get('hookSpecificOutput', {}).get('permissionDecision') != decision:
            raise ValueError('Guard hook self-check failed.')
    version=codex_version()
    if version != 'codex-cli 0.160.0':
        raise ValueError('This host profile is validated with codex-cli 0.160.0; review a different version before activation.')
    return {'codex_version':version,'hook_sha256': hashlib.sha256(hook.read_bytes()).hexdigest(),
            'policy_sha256': hashlib.sha256((Path(state)/'policy.json').read_bytes()).hexdigest(),
            'config': config}


def command(workspace, state, *, reviewed_hook=False):
    binary = shutil.which('codex')
    if binary is None:
        raise ValueError('Codex CLI was not found.')
    config = configuration(workspace, state)
    args = [binary, 'exec', '--ignore-user-config', '--ignore-rules', '--ephemeral',
            '--strict-config', '--skip-git-repo-check', '--sandbox', 'read-only',
            '--json', '-C', str(Path(workspace).resolve())]
    if reviewed_hook:
        # Only for an operator-reviewed, self-tested hook, not a sandbox bypass.
        args.append('--dangerously-bypass-hook-trust')
    for key, value in config.items():
        args += ['-c', key+'='+toml_value(value)]
    return args


def capture(args, prompt, output, timeout):
    """Bound a live session and reap its process group, including on interruption."""
    output=Path(output)
    with (output/'events.jsonl').open('w') as events, (output/'stderr.txt').open('w') as errors:
        process=subprocess.Popen([*args, '-'], stdin=subprocess.PIPE, text=True,
                                 stdout=events, stderr=errors, start_new_session=True)
        try:
            process.communicate(prompt, timeout=timeout)
            return process.returncode
        except subprocess.TimeoutExpired:
            return 124
        finally:
            # communicate() reaps a normally completed leader. Its PID/group
            # number may then be reused, so only signal while it is unreaped.
            if process.returncode is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait()
