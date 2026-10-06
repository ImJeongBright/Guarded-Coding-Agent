"""macOS Seatbelt backend. No unisolated fallback."""
import json
import os
from pathlib import Path
import resource
import re
import subprocess
import sys
import tempfile
from .domain import MAX_GIT_METADATA_OUTPUT, MAX_OUTPUT
from .execution import ExecutionFailure
from .process_lifecycle import ProcessScope, LifecycleUnavailable

class SandboxUnavailable(RuntimeError):
    pass

def clean_env(temp):
    return {'PATH':'/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin',
            'HOME':str(temp), 'TMPDIR':str(temp), 'LANG':'C', 'LC_ALL':'C',
            'GIT_CONFIG_NOSYSTEM':'1', 'GIT_CONFIG_GLOBAL':'/dev/null',
            'GIT_ATTR_NOSYSTEM':'1',
            'GIT_TERMINAL_PROMPT':'0', 'GIT_PAGER':'cat', 'GIT_EXTERNAL_DIFF':'',
            'GIT_OPTIONAL_LOCKS':'0'}

def profile(workspace, temp, executable, git=False, remote_path=None, network=False, trusted=(), write_paths=(), lifecycle=None):
    def sub(path):
        return '(subpath ' + json.dumps(str(Path(path).resolve()),ensure_ascii=False) + ')'
    runtime_roots=('/usr/bin','/usr/sbin','/usr/lib','/usr/libexec','/usr/share','/bin','/sbin',
                   '/System/Library','/Library/Frameworks','/Library/Developer','/opt/homebrew/Cellar',
                   '/opt/homebrew/opt','/opt/homebrew/bin','/opt/homebrew/lib','/dev')
    read = [sub(p) for p in runtime_roots if Path(p).exists()]
    # dyld requires read access to the root directory itself, not its descendants.
    read += ['(literal "/")', sub(workspace), sub(temp), '(literal '+json.dumps(executable,ensure_ascii=False)+')']
    # Apple's cc launcher reads only these machine-level developer selection links.
    read += ['(literal "/private/var/select/developer_dir")',
             '(literal "/private/var/db/xcode_select_link")', '(literal "/private/var/select/sh")']
    write = [sub(temp), '(literal "/dev/null")']
    if git:
        write.append(sub(Path(workspace)/'.git'))
    else:
        for relative in write_paths:
            candidate=Path(workspace)/relative
            if candidate.resolve()!=candidate:
                raise SandboxUnavailable('Command write scope changed to a symlink; no execution occurred.')
            # Keep the canonical workspace pathname fixed. A symlink swap must
            # never be realpath-expanded into a new permission outside it.
            expression='^'+re.escape(str(candidate))+'(/|$)'
            write.append('(regex '+json.dumps(expression,ensure_ascii=False)+')')
    if remote_path is not None:
        read.append(sub(remote_path))
        write.append(sub(remote_path))
    # Regex is applied to canonical paths, including descendants reached through symlinks.
    sensitive = r'(^|/)(\.env(\.[^/]*)?|\.ssh|\.aws|\.gnupg|credentials(\.[^/]*)?|id_rsa|id_ed25519|[^/]*\.(pem|key))(/|$)'
    protected = r'(^|/)(\.guard|\.agents|\.codex)(/|$)'
    ancestors=set()
    for path in (workspace,temp,remote_path,*runtime_roots):
        if path is not None:
            ancestors.update(str(p) for p in Path(path).resolve().parents)
    metadata=' '.join('(literal '+json.dumps(p,ensure_ascii=False)+')' for p in sorted(ancestors))
    lines = ['(version 1)', '(deny default)', '(allow process*)', '(allow sysctl-read)',
             '(allow mach-lookup)', '(allow file-read* '+ ' '.join(read)+')',
             '(allow file-read-metadata (literal "/private") (literal "/private/var") (literal "/private/var/select") (literal "/var") (literal "/var/select"))',
             '(allow file-read-metadata '+metadata+')',
             '(allow file-write* '+' '.join(write)+')',
             '(deny file-read* file-write* (regex '+json.dumps(sensitive)+'))',
             '(deny file-read* file-write* (regex '+json.dumps(protected)+'))']
    if not git:
        lines.append('(deny file-read* file-write* '+sub(Path(workspace)/'.git')+')')
    for path in trusted:
        lines.append('(deny file-read* file-write* '+sub(path)+')')
    if network:
        lines.append('(allow network*)')
    if lifecycle is not None:
        lines.append(lifecycle.policy())
    return '\n'.join(lines)

def run(argv, cwd, workspace, *, stdin='', timeout=20, git=False,
        remote_path=None, network=False, trusted=(), write_paths=(), output_limit=MAX_OUTPUT):
    if type(output_limit) is not int or not MAX_OUTPUT <= output_limit <= MAX_GIT_METADATA_OUTPUT:
        raise ValueError('Captured output limit is outside the bounded internal range.')
    if sys.platform != 'darwin' or not Path('/usr/bin/sandbox-exec').is_file():
        raise SandboxUnavailable('This release requires macOS sandbox-exec; no unsafe fallback exists.')
    try:
        scope = ProcessScope(excluded=(workspace,remote_path))
    except LifecycleUnavailable as error:
        raise SandboxUnavailable(str(error)) from error
    try:
        return _run(argv, cwd, workspace, scope, stdin=stdin, timeout=timeout, git=git,
                    remote_path=remote_path, network=network, trusted=trusted, write_paths=write_paths,
                    output_limit=output_limit)
    except LifecycleUnavailable as error:
        if scope.started:
            raise ExecutionFailure(str(error),executed=True,effect_status='possible',
                                   stage='process_cleanup',rule='SH-LIFECYCLE',exit_code=125) from error
        raise SandboxUnavailable(str(error)) from error
    except (ExecutionFailure,SandboxUnavailable):
        raise
    except Exception as error:
        if scope.started:
            raise ExecutionFailure(str(error),executed=True,effect_status='possible',
                                   stage='command_execution',exit_code=125) from error
        raise
    finally:
        try:
            scope.close()
        except OSError as error:
            if scope.started:
                raise ExecutionFailure(str(error),executed=True,effect_status='possible',
                                       stage='lifecycle_storage_cleanup',rule='SH-LIFECYCLE',exit_code=125) from error
            raise SandboxUnavailable(str(error)) from error

def _run(argv, cwd, workspace, scope, *, stdin, timeout, git, remote_path, network, trusted, write_paths,
         output_limit=MAX_OUTPUT):
    with tempfile.TemporaryDirectory(prefix='guard-command-', dir='/private/tmp') as temporary:
        env = clean_env(temporary)
        policy = profile(workspace, temporary, argv[0], git, remote_path, network, trusted, write_paths, lifecycle=scope)
        scope.selftest(policy,cwd,env)
        # On-disk spools keep subprocess output out of Python memory until bounded retrieval.
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            def limits():
                resource.setrlimit(resource.RLIMIT_FSIZE,(32*1024*1024,32*1024*1024))
            process = subprocess.Popen(['/usr/bin/sandbox-exec','-p',policy,*argv], cwd=cwd,
                                       env=env, stdin=subprocess.PIPE, stdout=output,
                                       stderr=errors, start_new_session=True, preexec_fn=limits)
            scope.started = True
            timed_out = False
            try:
                process.communicate(stdin.encode(), timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
            finally:
                # Kill only the pinned direct child here. Group IDs can be
                # reused after communicate() reaps the parent. Descendants are
                # handled below by atomic pid+version signals and policy scope.
                if process.poll() is None:
                    process.kill()
                process.wait()
                try:
                    descendants = scope.terminate()
                except LifecycleUnavailable as error:
                    raise ExecutionFailure(str(error)+' Marker directory retained: '+str(scope.directory),executed=True,effect_status='possible',
                                           stage='process_cleanup',rule='SH-LIFECYCLE',exit_code=125) from error
            output.seek(0)
            errors.seek(0)
            stdout = output.read(output_limit+1)
            stderr = errors.read(MAX_OUTPUT+1)
            return {'exit_code':124 if timed_out else process.returncode,
                    'stdout':stdout[:output_limit].decode(errors='replace'),
                    'stderr':stderr[:MAX_OUTPUT].decode(errors='replace'),
                    'timed_out':timed_out,
                    'effect_status':'possible',
                    'lifecycle_status':'terminated',
                    'terminated_scope_processes':descendants,
                    'output_truncated':len(stdout)>output_limit or len(stderr)>MAX_OUTPUT}
