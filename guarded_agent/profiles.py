"""Operator-only profile suggestions. Project metadata never grants capabilities."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from .domain import digest
from .gateway import Gateway


def _gateway(workspace, state):
    state = Path(state).resolve()
    return Gateway(workspace,state,policy_path=state/'policy.json' if (state/'policy.json').exists() else None)


def discover(workspace, state):
    g = _gateway(workspace,state)
    sources, commands, notes = {}, [], []

    def read(path):
        result = g.submit({'tool':'filesystem','operation':'read','path':path})
        if result['decision']=='DENY': return None
        sources[path] = result['sha256']
        return result['stdout']

    manifest = read('package.json') if (g.workspace/'package.json').exists() else None
    if manifest is not None:
        package = json.loads(manifest)
        script = package.get('scripts',{}).get('test')
        # No npm/shell/project script runs. Recognize only a fixed builtin Node test shape.
        match = re.fullmatch(r'node( --experimental-strip-types)? --test ((?:test|tests)/[A-Za-z0-9_./*\-]+\.test\.mjs)',script) if isinstance(script,str) else None
        if match and '..' not in Path(match[2]).parts and shutil.which('node'):
            argv = [str(Path(shutil.which('node')).resolve())]
            if match[1]: argv.append('--experimental-strip-types')
            argv.extend(['--test',match[2]])
            commands.append({'id':'node-tests','argv':argv,'cwd':'.','write_paths':[],
                             'filter':{'kind':'node-test-literal','position':len(argv)-1}})
        else:
            notes.append('Unrecognized test script: review and construct a narrow profile manually; nothing was executed.')
    # This detector is deliberately for the reviewed C DBMS layout, not a Makefile interpreter.
    if all((g.workspace/path).is_file() for path in ('Makefile','src/db.c','tests/test_db.py')):
        for path in ('Makefile','src/db.c','tests/test_db.py'):
            if read(path) is None: raise ValueError('C layout contains unavailable source paths.')
        cc = subprocess.check_output(['/usr/bin/xcrun','--find','cc'],text=True).strip()
        sdk = subprocess.check_output(['/usr/bin/xcrun','--show-sdk-path'],text=True).strip()
        argv = [cc,'-isysroot',sdk,'-std=c11','-Wall','-Wextra','-Werror','-pedantic','-O2','src/db.c','-o','build/minidb']
        debug = argv.copy(); debug[debug.index('-O2')]='-O0'; debug.insert(debug.index('-O0')+1,'-g')
        commands.extend([
            {'id':'c-build','argv':argv,'cwd':'.','write_paths':['build'],'variants':{'debug':debug}},
            {'id':'c-tests','argv':[str(Path(sys.executable).resolve()),'tests/test_db.py'],
             'cwd':'.','write_paths':['build/test-data'],'filter':{'kind':'python-unittest-literal','position':2}},
            {'id':'c-db','argv':[str(g.workspace/'build/minidb')],'cwd':'.','write_paths':['data.db','data.db.tmp']},
        ])
        notes.append('C DBMS layout detector proposes fixed compiler/test commands; it does not execute or interpret Makefile recipes. Review write scopes before applying.')
    candidate = {'workspace':str(g.workspace),'workspace_identity':list(g.fs.identity),
        'policy_digest':g.source_digest,'sources':sources,'commands':commands,'notes':notes}
    candidate['digest'] = digest(candidate)
    target = g.state/'profile-candidates.json'
    _atomic_json(target,candidate)
    return candidate


def apply_candidates(workspace, state, reviewed_digest, ids):
    g = _gateway(workspace,state)
    target = g.state/'profile-candidates.json'
    if target.is_symlink() or target.stat().st_nlink!=1 or target.stat().st_size>1_000_000:
        raise ValueError('Candidates must be a bounded ordinary file in operator state.')
    candidate = json.loads(target.read_text())
    checksum = candidate.pop('digest')
    if reviewed_digest!=checksum or digest(candidate)!=checksum:
        raise ValueError('Candidate digest differs from the reviewed proposal.')
    if candidate['workspace']!=str(g.workspace) or candidate['workspace_identity']!=list(g.fs.identity) or candidate['policy_digest']!=g.source_digest:
        raise ValueError('Workspace or policy changed; discover and review again.')
    for path,expected in candidate['sources'].items():
        result = g.submit({'tool':'filesystem','operation':'read','path':path})
        if result['decision']=='DENY' or result.get('sha256')!=expected:
            raise ValueError('Project metadata changed; discover and review again.')
    selected = [command for command in candidate['commands'] if command['id'] in ids]
    if not ids or len(set(ids))!=len(ids) or len(selected)!=len(ids):
        raise ValueError('Choose explicit unique profile ids from the reviewed candidates.')
    policy = json.loads(json.dumps(g.policy))
    policy['commands'] = [c for c in policy.get('commands',[]) if c.get('id') not in ids]+selected
    policy['version'] = '003-'+checksum[:12]
    # Validate all command capabilities before making the atomic operator policy update.
    Gateway(g.workspace,g.state,policy)
    _atomic_json(g.state/'policy.json',policy)
    return policy


def _atomic_json(target, value):
    fd, name = tempfile.mkstemp(prefix='.profile-',dir=target.parent)
    try:
        with os.fdopen(fd,'w') as stream:
            json.dump(value,stream,ensure_ascii=False,indent=2); stream.write('\n')
            stream.flush(); os.fsync(stream.fileno())
        os.replace(name,target)
    finally:
        if os.path.exists(name): os.unlink(name)
