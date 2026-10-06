import json
from pathlib import Path
import sys

root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root))
from guarded_agent.gateway import Gateway

case=Path(__file__).resolve().parent/'live/c'; work=case/'workspace'
code='''from pathlib import Path
import struct,subprocess,tempfile
binary=Path.cwd()/'build/minidb'
expected='Commands:\\ninsert <uint32 id> <name>\\nselect\\ncount\\nfind <uint32 id>\\n.help\\n.exit\\n'
with tempfile.TemporaryDirectory(dir=Path.cwd()/'build/test-data') as tmp:
 p=Path(tmp)
 def help_run(commands):
  r=subprocess.run([str(binary)],input=commands,text=True,capture_output=True,cwd=p,timeout=3)
  assert (r.returncode,r.stderr)==(0,''),(r.returncode,r.stderr)
  assert r.stdout==expected*commands.count('.help'),r.stdout
 for commands in ['.help\\n.exit\\n','.help\\n','.help\\n.help\\n.exit\\n']:
  help_run(commands)
  assert list(p.iterdir())==[],list(p.iterdir())
 db=p/'data.db'; content=b'GDB1'+struct.pack('<I',1)+struct.pack('<I32s',0,b'legacy')
 db.write_bytes(content)
 def snapshot():
  st=db.stat();return (db.read_bytes(),st.st_ino,st.st_mtime_ns,st.st_ctime_ns,st.st_size,st.st_mode)
 before=snapshot()
 for commands in ['.help\\n.exit\\n','.help\\n','.help\\n.help\\n.exit\\n']:
  help_run(commands)
  assert snapshot()==before,(snapshot(),before)
  assert [f.name for f in p.iterdir()]==['data.db']
print('Independent help contract passed: exact seven lines, repeated help, EOF/exit, empty/existing DB, bytes/inode/mtime/ctime/mode unchanged')
'''
argv=[str(Path(sys.executable).resolve()),'-B','-c',code]
policy=json.loads((case/'operator-state/policy.json').read_text())
policy['commands'].append({'argv':argv,'write_paths':['build/test-data']})
gateway=Gateway(work,case/'help-reviewer',policy,actor='independent-help-reviewer')
checks=[]
for mode in ('release','debug'):
 request=dict(tool='shell',operation='run',profile='c-build')
 if mode=='debug':request['mode']='debug'
 checks.append({'label':mode+' build',**gateway.submit(request)})
 checks.append({'label':mode+' independent help',**gateway.submit(dict(tool='shell',operation='exec',argv=argv))})
record={'checks':checks,'passed':all(r['executed'] and r['exit_code']==0 for r in checks)}
(case/'help-verification.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'passed':record['passed'],'checks':len(checks)}))
raise SystemExit(0 if record['passed'] else 1)
