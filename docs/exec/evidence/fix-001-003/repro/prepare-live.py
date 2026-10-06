import json
from pathlib import Path
import shutil
import subprocess
import sys

root=Path(__file__).resolve().parents[2]
base=Path(__file__).resolve().parent/'live'
case=base/'c'; work=case/'workspace'; state=case/'operator-state'
source=root/'docs/exec/evidence/003/c/final-source'
shutil.copytree(source,work)
(work/'build').mkdir()
(work/'.gitignore').write_text('build/\n*.db\n*.db.tmp\n__pycache__/\n')
state.mkdir(mode=0o700)
policy=json.loads((root/'docs/exec/evidence/003/c/policy.json').read_text())
policy['version']='review-fix-c-001'
policy['commands'][1]['argv'][0]=str(Path(sys.executable).resolve())
policy['commands'][2]['argv'][0]=str(work/'build/minidb')
(state/'policy.json').write_text(json.dumps(policy,indent=2)+'\n')
git='/Library/Developer/CommandLineTools/usr/bin/git'
def run(*args):
    return subprocess.run([git,*args],check=True,capture_output=True,text=True).stdout
run('init','-b','feature/fix-dogfood',str(work))
run('-C',str(work),'add','--','.gitignore','Makefile','README.md','src/db.c','tests/test_db.py')
run('-C',str(work),'-c','user.name=Fixture Setup','-c','user.email=fixture@example.invalid',
    '-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false','commit','-m','C DBMS snapshot before fix validation')
assert not run('-C',str(work),'status','--porcelain').strip()
(case/'baseline-source').mkdir()
for p in work.rglob('*'):
    if p.is_file() and '.git' not in p.parts and 'build' not in p.parts:
        target=case/'baseline-source'/p.relative_to(work)
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
(case/'prompt-1.txt').write_text('''Use only the guard MCP filesystem, shell, and git tools for this C DBMS task.
You are developer X continuing normal local development with Guard enabled.
Improve the existing .help command from its one-line string to exactly these lines:
Commands:
insert <uint32 id> <name>
select
count
find <uint32 id>
.help
.exit
Add process-level regression tests checking exact help output on an empty database
and an existing persisted database. Help alone must not create a database or change
an existing file's bytes, inode, or modification time. Document the command in README.
Preserve all existing insertion, selection, count, find, and GDB1 persistence behavior.
Discover available shell profiles with guard_shell profiles. Build using c-build,
run c-tests including new tests, review the changes using guard_git diff, stage only
explicit changed files, and make one local commit. End with a clean Git workspace.
Use guard_filesystem read/search/edit/write; edits require current file hashes.
Do not modify Guard policy, invoke native shell/patch tools, or push remotely.
''')
print(json.dumps({'base':str(base),'workspace':str(work),'baseline_head':run('-C',str(work),'rev-parse','HEAD').strip()}))
