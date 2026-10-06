import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from guarded_agent import sandbox

original = sandbox.profile
results = []
with tempfile.TemporaryDirectory(prefix='guard-lifecycle-probe-') as raw:
    work=Path(raw).resolve()
    (work/'main.c').write_text('#include <stdio.h>\nint main(void){puts("ok");return 0;}\n')
    for rules in ('(deny syscall-unix (syscall-number 82 147))',
                  '(deny syscall-unix (syscall-number 82 147 244) (with errno 78))'):
        def restricted(*args, **kw):
            return original(*args, **kw)+'\n'+rules
        cases={
            'detach':[str(Path(sys.executable).resolve()),'-c','import subprocess,sys;subprocess.run([sys.executable,"-c","print(123)"],start_new_session=True,check=True)'],
            'normal_child':[str(Path(sys.executable).resolve()),'-c','import subprocess,sys;subprocess.run([sys.executable,"-c","print(123)"],check=True)'],
            'posix_spawn':[str(Path(sys.executable).resolve()),'-c','import os; p=os.posix_spawn("/bin/echo",["echo","spawned"],os.environ,setpgroup=0);os.waitpid(p,0)'],
            'compile':['/Library/Developer/CommandLineTools/usr/bin/cc','-isysroot','/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk','main.c','-o','build/app'],
        }
        node=subprocess.check_output(['/bin/zsh','-c','command -v node'],text=True).strip()
        cases['node_spawn']=[node,'-e','const c=require("child_process").spawnSync("/bin/echo",["node-child"]); console.log(c.status,c.error?.code); process.exit(c.status??1)']
        (work/'build').mkdir(exist_ok=True)
        with patch('guarded_agent.sandbox.profile',side_effect=restricted):
            for label, argv in cases.items():
                result=sandbox.run(argv,work,work,write_paths=['build'],timeout=3)
                results.append({'rules':rules,'case':label,**result})
print(json.dumps(results,indent=2))
(ROOT/'.guard-runs/fix-001-003/lifecycle-probe.json').write_text(json.dumps(results,indent=2))
