"""Validate Darwin atomic identity signaling only against our own sleep child.

Primary definitions:
https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/proc_info_private.h
https://github.com/apple-oss-distributions/xnu/blob/main/libsyscall/wrappers/libproc/libproc.c
https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/proc_info.c
Local SDK libproc.h also declares proc_signal_with_audittoken.
"""
import ctypes
import errno
import json
from pathlib import Path
import signal
import subprocess


class UniqueInfo(ctypes.Structure):
    _fields_ = [('uuid', ctypes.c_ubyte*16),
                ('uniqueid', ctypes.c_uint64), ('parent_uniqueid', ctypes.c_uint64),
                ('pidversion', ctypes.c_int32), ('parent_pidversion', ctypes.c_int32),
                ('reserved2', ctypes.c_uint64), ('reserved3', ctypes.c_uint64)]


class AuditToken(ctypes.Structure):
    _fields_ = [('val', ctypes.c_uint32*8)]


def main():
    lib = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
    lib.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                                ctypes.c_void_p, ctypes.c_int]
    lib.proc_pidinfo.restype = ctypes.c_int
    lib.proc_signal_with_audittoken.argtypes = [ctypes.POINTER(AuditToken), ctypes.c_int]
    lib.proc_signal_with_audittoken.restype = ctypes.c_int
    assert ctypes.sizeof(UniqueInfo)==56
    assert ctypes.sizeof(AuditToken)==32
    child = subprocess.Popen(['/bin/sleep', '10'])
    try:
        info = UniqueInfo()
        size = lib.proc_pidinfo(child.pid, 17, 0, ctypes.byref(info), ctypes.sizeof(info))
        assert size==ctypes.sizeof(info), (size, ctypes.get_errno())
        forged = AuditToken()
        forged.val[5] = child.pid
        forged.val[7] = (info.pidversion+1) & 0xffffffff
        ctypes.set_errno(0)
        rejected = lib.proc_signal_with_audittoken(ctypes.byref(forged), signal.SIGTERM)
        rejected_errno = ctypes.get_errno()
        # Unlike kill(), the libproc wrapper returns the errno value on error.
        assert rejected==errno.ESRCH, (rejected, rejected_errno)
        alive_after_forged = child.poll() is None
        assert alive_after_forged
        actual = AuditToken()
        actual.val[5] = child.pid
        actual.val[7] = info.pidversion
        ctypes.set_errno(0)
        success = lib.proc_signal_with_audittoken(ctypes.byref(actual), signal.SIGTERM)
        success_errno = ctypes.get_errno()
        assert success==0, (success, success_errno)
        child.wait(timeout=5)
        assert child.returncode==-signal.SIGTERM, child.returncode
        result = {'passed':True, 'unique_info_size':size,
                  'audit_token_size':ctypes.sizeof(AuditToken),
                  'pid_slot':5, 'pidversion_slot':7,
                  'forged_version_result':rejected, 'forged_version_errno':rejected_errno,
                  'own_child_alive_after_forged':alive_after_forged,
                  'valid_token_result':success, 'valid_token_errno':success_errno,
                  'own_child_exit':child.returncode,
                  'unrelated_processes_signaled':0}
        Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result))
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()


if __name__=='__main__':
    main()
