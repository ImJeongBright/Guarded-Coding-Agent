import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import uuid

ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from guarded_agent.sandbox import profile, clean_env

sb=ctypes.CDLL('/usr/lib/libsandbox.dylib',use_errno=True)
sb.sandbox_check.restype=ctypes.c_int
sb.sandbox_check.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int]
quiet=ctypes.c_int.in_dll(sb,'SANDBOX_CHECK_NO_REPORT').value
identifier=uuid.uuid4().hex
yes='/dev/guard-'+identifier+'-yes'; no='/dev/guard-'+identifier+'-no'
def check(pid):
    return [sb.sandbox_check(pid,b'file-read-metadata',1|quiet,ctypes.c_char_p(path.encode())) for path in (yes,no)]
results={'quiet':quiet}
with tempfile.TemporaryDirectory(prefix='guard-marker-probe-') as raw:
    work=Path(raw).resolve(); (work/'output').mkdir()
    yes=str(work/'allowed'); no=str(work/'denied')
    Path(yes).write_text('metadata-marker'); Path(no).write_text('metadata-marker')
    results['host']=check(os.getpid())
    apply_source = '''import ctypes,os
class Profile(ctypes.Structure):
 _fields_=[('builtin',ctypes.c_char_p),('data',ctypes.c_void_p),('size',ctypes.c_size_t),('available',ctypes.c_size_t)]
l=ctypes.CDLL('/usr/lib/libsandbox.dylib');e=ctypes.c_char_p()
l.sandbox_compile_string.argtypes=[ctypes.c_char_p,ctypes.c_void_p,ctypes.POINTER(ctypes.c_char_p)];l.sandbox_compile_string.restype=ctypes.POINTER(Profile)
l.sandbox_apply_bytecode.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_char_p];l.sandbox_apply_bytecode.restype=ctypes.c_int
p=l.sandbox_compile_string(PROFILE,None,ctypes.byref(e))
if not p: raise RuntimeError(e.value)
r=l.sandbox_apply_bytecode(p.contents.data,p.contents.size,None)
os._exit(42 if r==0 else 0)
'''
    for label,source in {
        'setsid':'import subprocess,sys; p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(0.8)"],start_new_session=True); print(p.pid,flush=True)',
        'spawn':'import os; print(os.posix_spawn("/bin/sleep",["sleep","0.8"],os.environ,setpgroup=0),flush=True)',
        'resandbox':'import ctypes; l=ctypes.CDLL("/usr/lib/libsandbox.dylib"); e=ctypes.c_char_p(); r=l.sandbox_init(b"(version 1)(allow default)",0,ctypes.byref(e)); print(r,e.value)',
        'narrow_resandbox':'import ctypes,os; l=ctypes.CDLL("/usr/lib/libsandbox.dylib"); e=ctypes.c_char_p(); r=l.sandbox_init(b"(version 1)(deny default)",0,ctypes.byref(e)); os._exit(42 if r==0 else 0)',
        'narrow_apply_bytecode':apply_source.replace('PROFILE',repr(b'(version 1)(deny default)')),
        'permissive_apply_bytecode':apply_source.replace('PROFILE',repr(b'(version 1)(allow default)')),
    }.items():
        argv=[str(Path(sys.executable).resolve()),'-c',source]
        rules=profile(work,work,argv[0],write_paths=['output'])+'\n'+f'(allow file-read-metadata (literal "{yes}"))\n(deny file-read-metadata (literal "{no}"))'
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            p=subprocess.Popen(['/usr/bin/sandbox-exec','-p',rules,*argv],cwd=work,env=clean_env(work),stdout=output,stderr=errors,start_new_session=True)
            p.wait(timeout=2)
            output.seek(0); errors.seek(0)
            out,err=output.read().decode(),errors.read().decode()
        record={'exit_code':p.returncode,'stdout':out,'stderr':err}
        if out.strip().isdigit():
            child=int(out.strip()); record['child_policy']=check(child)
            if record['child_policy']==[0,1]:
                try: os.kill(child,signal.SIGKILL)
                except ProcessLookupError: pass
        results[label]=record
print(json.dumps(results,indent=2))
(ROOT/'.guard-runs/fix-001-003/marker-probe.json').write_text(json.dumps(results,indent=2))
