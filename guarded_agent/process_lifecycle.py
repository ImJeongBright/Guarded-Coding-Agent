"""Darwin process cleanup by inherited Seatbelt identity, including detached children.

The two metadata-only marker files are outside all command write scopes. A
native self-test requires this OS to reject replacing/stacking the applied
profile, so a command cannot mask its inherited identity. Process trees and
process groups alone cannot identify already reparented children.
"""
import ctypes
import errno
from functools import lru_cache
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import uuid


class LifecycleUnavailable(RuntimeError):
    pass


class _LifecycleRace(RuntimeError):
    """An exec/reuse race makes a scan inconclusive, rather than empty."""
    pass


class _BSDInfo(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in (
        'flags', 'status', 'xstatus', 'pid', 'ppid', 'uid', 'gid', 'ruid',
        'rgid', 'svuid', 'svgid', 'reserved')]+[
        ('comm', ctypes.c_char*16), ('name', ctypes.c_char*32),
        ('nfiles', ctypes.c_uint32), ('pgid', ctypes.c_uint32),
        ('jobc', ctypes.c_uint32), ('tdev', ctypes.c_uint32),
        ('tpgid', ctypes.c_uint32), ('nice', ctypes.c_int32),
        ('start_sec', ctypes.c_uint64), ('start_usec', ctypes.c_uint64)]


class _UniqueInfo(ctypes.Structure):
    _fields_ = [('uuid', ctypes.c_ubyte*16), ('uniqueid', ctypes.c_uint64),
                ('parent_uniqueid', ctypes.c_uint64), ('version', ctypes.c_int32),
                ('parent_version', ctypes.c_int32), ('reserved2', ctypes.c_uint64),
                ('reserved3', ctypes.c_uint64)]


class _AuditToken(ctypes.Structure):
    _fields_ = [('val', ctypes.c_uint32*8)]


@lru_cache(maxsize=1)
def _backend():
    try:
        sandbox = ctypes.CDLL('/usr/lib/libsandbox.dylib', use_errno=True)
        proc = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
        sandbox.sandbox_check.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        sandbox.sandbox_check.restype = ctypes.c_int
        quiet = ctypes.c_int.in_dll(sandbox, 'SANDBOX_CHECK_NO_REPORT').value
        proc.proc_listpids.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_int]
        proc.proc_listpids.restype = ctypes.c_int
        proc.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
        proc.proc_pidinfo.restype = ctypes.c_int
        proc.proc_signal_with_audittoken.argtypes = [ctypes.POINTER(_AuditToken), ctypes.c_int]
        proc.proc_signal_with_audittoken.restype = ctypes.c_int
        if (ctypes.sizeof(_BSDInfo), ctypes.sizeof(_UniqueInfo), ctypes.sizeof(_AuditToken)) != (136, 56, 32):
            raise ValueError('Unexpected Darwin proc_bsdinfo layout.')
        return sandbox, proc, quiet
    except (OSError, AttributeError, ValueError) as error:
        raise LifecycleUnavailable('Darwin process inspection is unavailable.') from error


class ProcessScope:
    MAX_PIDS = 65_536
    CLEANUP_TIMEOUT = 2.0
    _immutability_proven = False

    def __init__(self, *, excluded=()):
        self.sandbox, self.proc, self.quiet = _backend()
        # Do not inherit TMPDIR: it can point at an agent-writable build directory.
        self.directory = Path(tempfile.mkdtemp(prefix='guard-lifecycle-', dir='/private/tmp'))
        self.allowed = self.directory/uuid.uuid4().hex
        self.denied = self.directory/uuid.uuid4().hex
        self.cleaned = False
        self.started = False
        try:
            parent = self.directory.resolve()
            if any(parent == Path(root).resolve() or Path(root).resolve() in parent.parents for root in excluded if root):
                raise LifecycleUnavailable('Lifecycle markers overlap an agent capability.')
            self.allowed.write_bytes(b'policy identity only')
            self.denied.write_bytes(b'policy identity only')
            if self._checks(os.getpid()) != (0, 0):
                raise LifecycleUnavailable('Guard host cannot inspect its lifecycle markers.')
            self._info(os.getpid())
            # Validate enumeration/query access before launching any command.
            deadline = time.monotonic()+self.CLEANUP_TIMEOUT
            while True:
                try:
                    self.members()
                    break
                except _LifecycleRace:
                    if time.monotonic() >= deadline:
                        raise LifecycleUnavailable('Process inspection did not stabilize before work.')
                    time.sleep(0.002)
        except BaseException:
            self._remove_directory()
            raise

    def policy(self):
        return '\n'.join([
            '(allow file-read-metadata (literal '+json.dumps(str(self.allowed))+'))',
            '(deny file-read-metadata (literal '+json.dumps(str(self.denied))+'))'])

    def _info(self, pid):
        info = _BSDInfo()
        ctypes.set_errno(0)
        size = self.proc.proc_pidinfo(pid, 3, 0, ctypes.byref(info), ctypes.sizeof(info))
        if size == 0 and ctypes.get_errno() in (errno.ESRCH, errno.ENOENT):
            return None
        if size != ctypes.sizeof(info) or info.pid != pid or info.uid != os.getuid():
            raise LifecycleUnavailable('Cannot inspect a live same-user process safely.')
        if info.start_usec >= 1_000_000 or not info.start_sec:
            raise LifecycleUnavailable('Malformed process birth identity.')
        return info

    def _checks(self, pid):
        values = []
        for path in (self.allowed, self.denied):
            ctypes.set_errno(0)
            result = self.sandbox.sandbox_check(pid, b'file-read-metadata', 1 | self.quiet,
                                                ctypes.c_char_p(os.fsencode(path)))
            if result not in (0, 1):
                if ctypes.get_errno() in (errno.ESRCH, errno.ENOENT):
                    return None
                raise LifecycleUnavailable('Cannot inspect process Seatbelt identity.')
            values.append(result)
        return tuple(values)

    def _unique(self, pid):
        info = _UniqueInfo()
        ctypes.set_errno(0)
        size = self.proc.proc_pidinfo(pid, 17, 0, ctypes.byref(info), ctypes.sizeof(info))
        if size == 0 and ctypes.get_errno() in (errno.ESRCH, errno.ENOENT):
            return None
        if size != ctypes.sizeof(info) or not info.uniqueid:
            raise LifecycleUnavailable('Cannot inspect process pidversion safely.')
        return info

    def _member(self, pid):
        before = self._unique(pid)
        if before is None:
            return None
        info = self._info(pid)
        checks = self._checks(pid) if info is not None and info.status != 5 else None
        after = self._unique(pid)
        if after is None:
            return None
        if (before.uniqueid, before.version) != (after.uniqueid, after.version) or info is None:
            raise _LifecycleRace('Process lifetime changed during inspection.')
        if info.status == 5:
            return None
        if checks is None:
            raise _LifecycleRace('Process disappeared during its sandbox identity check.')
        if checks != (0, 1):
            return None
        if pid == os.getpid():
            raise LifecycleUnavailable('Refusing to signal the Guard host.')
        return (pid, before.version, before.uniqueid)

    def _pids(self):
        capacity = 1024
        while capacity <= self.MAX_PIDS:
            buffer = (ctypes.c_int*capacity)()
            ctypes.set_errno(0)
            size = self.proc.proc_listpids(4, os.getuid(), buffer, ctypes.sizeof(buffer))
            if size <= 0 or size % ctypes.sizeof(ctypes.c_int):
                raise LifecycleUnavailable('Cannot enumerate same-user processes.')
            if size < ctypes.sizeof(buffer):
                return [pid for pid in buffer[:size//ctypes.sizeof(ctypes.c_int)] if pid > 0]
            capacity *= 2
        raise LifecycleUnavailable('Process enumeration exceeded the lifecycle bound.')

    def members(self):
        members = []
        for pid in self._pids():
            # Inspect all own processes; query errors cannot mean "not a member".
            identity = self._member(pid)
            if identity is not None:
                members.append(identity)
        return members

    def _signal(self, identity, kind):
        if self._member(identity[0]) != identity:
            return False
        token = _AuditToken()
        token.val[5], token.val[7] = identity[0], identity[1] & 0xffffffff
        # The kernel matches pid AND pidversion atomically before signaling.
        # This wrapper returns an errno value on failure, rather than -1.
        result = self.proc.proc_signal_with_audittoken(ctypes.byref(token), kind)
        if result == errno.ESRCH:  # Exit or exec raced us; a rescan sees any new lifetime.
            return False
        if result != 0:
            raise LifecycleUnavailable('Cannot signal a command process by its audit identity.')
        return True

    def selftest(self, policy, cwd, env):
        """Prove native membership, signaling and profile-immutability before work."""
        process = subprocess.Popen(['/usr/bin/sandbox-exec', '-p', policy, '/bin/sleep', '2'],
                                   cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                   start_new_session=True)
        try:
            deadline = time.monotonic()+1.0
            while time.monotonic() < deadline and process.poll() is None:
                try:
                    identity = self._member(process.pid)
                except _LifecycleRace:
                    identity = None
                if identity is not None:
                    try:
                        if self._signal(identity, signal.SIGSTOP) and self._signal(identity, signal.SIGCONT):
                            break
                    except _LifecycleRace:
                        pass
                    # sandbox-exec can exec the trusted sleep between these
                    # checks. Retry that identity; it is not a backend failure.
                time.sleep(0.002)
            else:
                stderr = process.stderr.read(2000) if process.poll() is not None else b''
                raise LifecycleUnavailable('Process lifecycle self-test could not apply Seatbelt: '+stderr.decode(errors='replace'))
        finally:
            # This fixed trusted direct child stays unreaped until wait(), so
            # Popen.kill cannot signal a reused PID. No untrusted work ran yet.
            if process.poll() is None:
                process.kill()
            process.wait()
            process.stderr.close()
        if not type(self)._immutability_proven:
            # Restricting __mac_syscall wholesale breaks legitimate dyld/ld
            # permission queries. Instead prove the kernel refuses both public
            # initialization and private bytecode apply after the first profile.
            code = '''import ctypes,os
class Profile(ctypes.Structure):
 _fields_=[('builtin',ctypes.c_char_p),('data',ctypes.c_void_p),('size',ctypes.c_size_t),('available',ctypes.c_size_t)]
l=ctypes.CDLL('/usr/lib/libsandbox.dylib');error=ctypes.c_char_p()
l.sandbox_init.argtypes=[ctypes.c_char_p,ctypes.c_uint64,ctypes.POINTER(ctypes.c_char_p)]
l.sandbox_compile_string.argtypes=[ctypes.c_char_p,ctypes.c_void_p,ctypes.POINTER(ctypes.c_char_p)]
l.sandbox_compile_string.restype=ctypes.POINTER(Profile)
l.sandbox_apply_bytecode.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_char_p]
for text in [b'(version 1)(deny default)',b'(version 1)(allow default)']:
 if l.sandbox_init(text,0,ctypes.byref(error))==0:os._exit(42)
 p=l.sandbox_compile_string(text,None,ctypes.byref(error))
 if not p:os._exit(43)
 if l.sandbox_apply_bytecode(p.contents.data,p.contents.size,None)==0:os._exit(42)
os._exit(0)
'''
            result = subprocess.run(['/usr/bin/sandbox-exec','-p',policy,sys.executable,'-I','-B','-c',code],
                                    cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                                    stderr=subprocess.PIPE,timeout=2)
            if result.returncode != 0:
                raise LifecycleUnavailable('This OS does not prove immutable command sandbox identity.')
            type(self)._immutability_proven = True

    def terminate(self):
        deadline = time.monotonic()+self.CLEANUP_TIMEOUT
        empty = 0
        terminated = set()
        while time.monotonic() < deadline:
            try:
                members = self.members()
            except _LifecycleRace:
                empty = 0
                time.sleep(0.002)
                continue
            if not members:
                empty += 1
                if empty == 2:
                    self.cleaned = True
                    return len(terminated)
            else:
                empty = 0
                # Freeze all currently visible members before killing. Rescans
                # include children forked between enumeration and SIGSTOP.
                for kind in (signal.SIGSTOP, signal.SIGKILL):
                    for identity in members:
                        try:
                            if self._signal(identity, kind) and kind == signal.SIGKILL:
                                terminated.add(identity)
                        except _LifecycleRace:
                            # The next scan must identify this new exec lifetime.
                            pass
            time.sleep(0.002)
        raise LifecycleUnavailable('Command process cleanup did not converge; host is unsafe for another action.')

    def close(self):
        # Keep markers when cleanup fails so a diagnostic/recovery can identify
        # remaining scope processes; never turn an inspection failure into success.
        if self.cleaned or not self.started:
            self._remove_directory()
        else:
            # Preserve the protected marker names for operator diagnostics and
            # identity-based recovery if native inspection failed after launch.
            record = {'format':1,'owner_uid':os.getuid(),
                      'allowed':str(self.allowed),'denied':str(self.denied)}
            (self.directory/'scope.json').write_text(json.dumps(record)+'\n')

    def _remove_directory(self):
        try:
            shutil.rmtree(self.directory)
        except FileNotFoundError:
            pass
