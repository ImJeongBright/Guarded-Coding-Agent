"""All traversal uses directory descriptors and O_NOFOLLOW, including writes."""
from contextlib import contextmanager
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid
from .domain import Action, MAX_CONTENT, MAX_OUTPUT
from .execution import ExecutionFailure

SENSITIVE = re.compile(r'^(?:\.env(?:\..*)?|\.ssh|\.aws|\.gnupg|credentials(?:\..*)?|id_(?:rsa|ed25519)|.*\.(?:pem|key))$', re.I)
PROTECTED = {'.git', '.guard', '.agents', '.codex'}

class Blocked(ValueError):
    def __init__(self, rule, reason):
        super().__init__(reason)
        self.rule = rule


class _Effects:
    def __init__(self):
        self.executed = False
        self.effect_status = 'none'
        self.stage = 'precheck'

    def changed(self, stage, status='partial'):
        self.executed = True
        self.effect_status = status
        self.stage = stage

    def result(self):
        return {'effect_status':self.effect_status, 'execution_stage':self.stage}

def classify_parts(parts):
    if any(SENSITIVE.fullmatch(p) for p in parts):
        raise Blocked('FS-SENSITIVE', 'Sensitive paths are outside the agent capability.')
    if any(p.casefold() in PROTECTED for p in parts):
        raise Blocked('FS-TRUSTED', 'Git metadata and guard configuration are protected.')

class Filesystem:
    def __init__(self, workspace, trusted_paths=()):
        self.root = Path(workspace).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError('Workspace must be a directory.')
        self.identity = (self.root.stat().st_dev, self.root.stat().st_ino)
        self.trusted = [Path(p).resolve() for p in trusted_paths]

    def check_workspace_links(self, *, reject_gitattributes=False):
        """Verify the tree without following links; optionally reject Git attributes.

        Git attributes can introduce content filters and are therefore checked in
        the same bounded traversal as link integrity. Traversal errors fail closed.
        """
        def on_error(_error):
            raise Blocked('FS-LINK', 'Workspace integrity could not be verified.')

        for root, directories, files in os.walk(self.root, followlinks=False, onerror=on_error):
            for name in directories + files:
                path = Path(root) / name
                try:
                    info = path.lstat()
                except OSError:
                    raise Blocked('FS-LINK', 'Workspace integrity could not be verified.')
                if stat.S_ISLNK(info.st_mode) or (stat.S_ISREG(info.st_mode) and info.st_nlink != 1):
                    raise Blocked('FS-LINK', 'Shell/Git require a workspace without symlinks or hardlinked files.')
                if reject_gitattributes and name == '.gitattributes':
                    raise Blocked('GT-CONFIG', 'Git attributes require a separate reviewed profile.')

    def relative(self, raw):
        p = Path(raw)
        lexical = Path(os.path.abspath(p if p.is_absolute() else self.root / p))
        # Inspect the original path too; traversal must not hide a sensitive component.
        classify_parts(p.parts)
        try:
            rel = lexical.relative_to(self.root)
            resolved = lexical.resolve()
            resolved.relative_to(self.root)
        except (ValueError, RuntimeError, OSError):
            raise Blocked('FS-SCOPE', 'Target must resolve inside the workspace.')
        classify_parts(rel.parts)
        classify_parts(resolved.relative_to(self.root).parts)
        def overlaps(candidate, trusted):
            c, t = str(candidate).casefold(), str(trusted).casefold()
            return c == t or c.startswith(t + os.sep)
        if any(overlaps(lexical,t) or overlaps(resolved,t) for t in self.trusted):
            raise Blocked('FS-TRUSTED', 'Guard runtime and state are protected.')
        current = self.root
        for part in rel.parts:
            current /= part
            if current.is_symlink():
                raise Blocked('FS-LINK', 'Symlink paths are unsupported; use an ordinary workspace path.')
            if current.is_file() and current.stat().st_nlink != 1:
                raise Blocked('FS-LINK', 'Hardlinked files are outside the capability.')
        return str(rel)

    def normalize(self, request):
        rel = self.relative(request['path'])
        operation = request['operation']
        if rel == '.' and operation not in ('list','search'):
            raise Blocked('FS-DELETE', 'Only list/search may target the workspace root.')
        data = {**request, 'path':rel}
        data.pop('tool'); data.pop('operation')
        if operation=='read':
            if 'end_line' in data and 'start_line' not in data:
                raise Blocked('FS-RANGE','end_line requires start_line.')
            if 'start_line' in data:
                data.setdefault('end_line',data['start_line']+199)
                if not 0 <= data['end_line']-data['start_line'] < 500:
                    raise Blocked('FS-RANGE','Read a range of at most 500 lines.')
        if operation=='search':
            query, pattern = data['query'], data.get('glob','*')
            if len(query)>256 or '\n' in query:
                raise Blocked('FS-SEARCH','Use a literal single-line query of at most 256 characters; empty query lists matching file paths.')
            if not pattern or len(pattern)>128 or pattern.startswith('/') or '..' in Path(pattern).parts or '\n' in pattern:
                raise Blocked('FS-SEARCH','Search glob must be a bounded relative pattern.')
            base = Path(rel)
            excludes = []
            if data.get('exclude_dirs') and not (self.root/base).is_dir():
                raise Blocked('FS-SEARCH','Directory exclusions require a directory search path.')
            for raw_exclude in data.get('exclude_dirs',[]):
                exclude = Path(raw_exclude)
                if exclude.is_absolute() or not exclude.parts or '..' in exclude.parts or str(exclude)=='.':
                    raise Blocked('FS-SEARCH','exclude_dirs must name literal directories relative to the search path.')
                candidate = str(base/exclude)
                candidate_rel = self.relative(candidate)
                try:
                    Path(candidate_rel).relative_to(base)
                except ValueError:
                    raise Blocked('FS-SEARCH','Excluded directories must stay below the search path.')
                if candidate_rel == rel:
                    raise Blocked('FS-SEARCH','The search root cannot exclude itself.')
                target = self.root/candidate_rel
                if target.exists() and not target.is_dir():
                    raise Blocked('FS-SEARCH','exclude_dirs entries must be directories when they exist.')
                excludes.append(candidate_rel)
            data['exclude_dirs'] = sorted(set(excludes))
        if operation=='edit':
            if not data['old_text'] or not re.fullmatch('[0-9a-f]{64}',data['expected_sha256']):
                raise Blocked('FS-EDIT','Edit requires non-empty old_text and the sha256 from a previous read.')
        return Action('filesystem', request['operation'], data)

    @contextmanager
    def parent(self, rel, create=False, effects=None):
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            if (os.fstat(fd).st_dev, os.fstat(fd).st_ino) != self.identity:
                raise Blocked('FS-SCOPE', 'Workspace identity changed.')
            parts = Path(rel).parts
            for part in parts[:-1]:
                if create:
                    try:
                        if effects is not None:
                            effects.stage = 'write_parent_create'
                        os.mkdir(part, dir_fd=fd)
                        if effects is not None:
                            effects.changed('write_parent_created')
                    except FileExistsError:
                        pass
                if effects is not None:
                    effects.stage = 'parent_open'
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = next_fd
            yield fd, parts[-1] if parts else '.'
        finally:
            os.close(fd)

    @staticmethod
    def read_bytes(fd, maximum=MAX_CONTENT):
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise Blocked('FS-LINK','Only an ordinary file with one link is allowed.')
        if info.st_size > MAX_CONTENT:
            raise Blocked('FS-SIZE','File exceeds the read size limit.')
        if info.st_size > maximum:
            raise Blocked('FS-SEARCH-BUDGET','File grew beyond the remaining search byte budget.')
        os.lseek(fd,0,os.SEEK_SET)
        with os.fdopen(os.dup(fd),'rb') as stream:
            raw = stream.read(maximum+1)
        if len(raw)>maximum:
            if maximum<MAX_CONTENT:
                raise Blocked('FS-SEARCH-BUDGET','File grew beyond the remaining search byte budget.')
            raise Blocked('FS-SIZE','File grew beyond the read size limit.')
        return raw

    def _edit(self, parent, name, data, effects):
        fd = os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
        temporary = None
        try:
            info = os.fstat(fd)
            original = self.read_bytes(fd)
            if hashlib.sha256(original).hexdigest()!=data['expected_sha256']:
                raise Blocked('FS-STALE','File changed since read; read it again before editing.')
            try:
                text = original.decode('utf-8')
            except UnicodeDecodeError:
                raise Blocked('FS-EDIT','Partial edit requires UTF-8 text.')
            if text.count(data['old_text'])!=1:
                raise Blocked('FS-EDIT','old_text must match exactly one occurrence; include more context.')
            replacement = text.replace(data['old_text'],data['new_text'],1).encode()
            if len(replacement)>MAX_CONTENT:
                raise Blocked('FS-SIZE','Edited file exceeds the content limit.')
            candidate = '.guard-edit-'+uuid.uuid4().hex
            out = os.open(candidate,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
            temporary = candidate  # Cleanup only files this operation successfully created.
            with os.fdopen(out,'wb') as stream:
                stream.write(replacement); stream.flush()
                os.fchmod(stream.fileno(),stat.S_IMODE(info.st_mode)&0o777)
                os.fsync(stream.fileno())
            current = os.stat(name,dir_fd=parent,follow_symlinks=False)
            if (current.st_dev,current.st_ino)!=(info.st_dev,info.st_ino) or current.st_nlink!=1 or self.read_bytes(fd)!=original:
                raise Blocked('FS-STALE','File changed during edit; no replacement was made.')
            os.replace(temporary,name,src_dir_fd=parent,dst_dir_fd=parent)
            temporary = None
            effects.changed('edit_directory_fsync','applied')
            os.fsync(parent)
            return {'exit_code':0,'stdout':'Edited one unique occurrence.','stderr':'',
                    'sha256':hashlib.sha256(replacement).hexdigest(),**effects.result()}
        finally:
            try:
                if temporary is not None:
                    try:
                        os.unlink(temporary,dir_fd=parent)
                    except OSError:
                        effects.changed('edit_temporary_cleanup')
                        raise
            finally:
                os.close(fd)

    def _search(self, rel, data):
        matches, budget = [], {'entries':0,'bytes':0,'output':0,'stop':False,'oversized':0}
        reasons = set()
        pattern = data.get('glob','*')
        excluded = set(data.get('exclude_dirs',[]))

        def append(match):
            size = len(json.dumps(match,ensure_ascii=False).encode())+2
            if len(matches)>=200:
                reasons.add('match_limit'); budget['stop']=True
            elif budget['output']+size>MAX_OUTPUT:
                reasons.add('output_limit'); budget['stop']=True
            else:
                matches.append(match); budget['output']+=size

        def scan(fd, path, direct=False):
            info = os.fstat(fd)
            if stat.S_ISDIR(info.st_mode):
                entries = []
                with os.scandir(fd) as iterator:
                    for entry in iterator:
                        if budget['entries']>=5000:
                            reasons.add('entry_limit'); break
                        budget['entries'] += 1
                        entries.append(entry.name)
                for name in sorted(entries):
                    # Exhausting enumeration does not discard collected entries.
                    if budget['stop']: break
                    child = str(Path(path)/name)
                    if child in excluded:
                        continue
                    try:
                        self.relative(child)
                        child_fd = os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
                    except (Blocked,OSError):
                        continue
                    try: scan(child_fd,child)
                    finally: os.close(child_fd)
            elif stat.S_ISREG(info.st_mode) and info.st_nlink==1 and fnmatch.fnmatchcase(path,pattern):
                if not data['query']:
                    append({'path':path}); return
                if info.st_size>MAX_CONTENT:
                    if direct:
                        raise Blocked('FS-SIZE','File exceeds the search size limit.')
                    budget['oversized']+=1; reasons.add('file_size_limit'); return
                if budget['bytes']+info.st_size>8_000_000:
                    reasons.add('byte_limit'); budget['stop']=True; return
                try:
                    raw = self.read_bytes(fd,maximum=min(MAX_CONTENT,8_000_000-budget['bytes']))
                except Blocked as error:
                    if error.rule=='FS-SEARCH-BUDGET':
                        reasons.add('byte_limit'); budget['stop']=True; return
                    if direct or error.rule!='FS-SIZE': raise
                    budget['oversized']+=1; reasons.add('file_size_limit'); return
                budget['bytes']+=len(raw)
                if b'\0' in raw: return
                try: text = raw.decode('utf-8')
                except UnicodeDecodeError: return
                for number,line in enumerate(text.splitlines(),1):
                    if data['query'] not in line: continue
                    match = {'path':path,'line':number,'text':line[:300]}
                    append(match)
                    if budget['stop']: return

        with self.parent(rel) as (parent,name):
            fd = os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
            try: scan(fd,rel,direct=True)
            finally: os.close(fd)
        return {'exit_code':0,'stdout':'','stderr':'','matches':matches,
                'truncated':bool(reasons),'incomplete':bool(reasons),
                'truncation_reasons':sorted(reasons),'skipped_oversized_files':budget['oversized'],
                'scanned_entries':budget['entries'],'scanned_bytes':budget['bytes'],
                'excluded_dirs':sorted(excluded)}

    @staticmethod
    def _list(fd):
        names, reasons = [], set()
        scanned = 0
        with os.scandir(fd) as iterator:
            for entry in iterator:
                if scanned>=5000:
                    reasons.add('entry_limit'); break
                scanned += 1
                try:
                    classify_parts((entry.name,))
                except Blocked:
                    continue
                names.append(entry.name)
        output, size = [], 0
        for name in sorted(names):
            encoded_size = len(name.encode('utf-8')) + (1 if output else 0)
            if len(output)>=2000:
                reasons.add('result_limit'); break
            if size+encoded_size>MAX_OUTPUT:
                reasons.add('output_limit'); break
            output.append(name); size+=encoded_size
        return {'exit_code':0,'stdout':'\n'.join(output),'stderr':'',
                'truncated':bool(reasons),'incomplete':bool(reasons),
                'truncation_reasons':sorted(reasons),'scanned_entries':scanned,
                'returned_entries':len(output)}

    def _execute(self, action):
        effects = _Effects()
        try:
            return self._execute_inner(action,effects)
        except Exception as error:
            if effects.executed:
                raise ExecutionFailure(str(error),executed=True,effect_status=effects.effect_status,
                                       stage=effects.stage,rule=getattr(error,'rule','EXEC-ERROR')) from error
            raise

    def _execute_inner(self, action, effects):
        rel = self.relative(action.data['path'])
        operation = action.operation
        if operation=='search':
            return self._search(rel,action.data)
        with self.parent(rel, create=operation=='write', effects=effects) as (parent, name):
            if operation=='edit':
                return self._edit(parent,name,action.data,effects)
            if operation == 'delete':
                info = os.stat(name, dir_fd=parent, follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise Blocked('FS-DELETE', 'Only a single ordinary file may be deleted.')
                os.unlink(name, dir_fd=parent)
                effects.changed('delete_completed','applied')
                return {'exit_code':0, 'stdout':'Deleted one file.', 'stderr':'',**effects.result()}
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if operation == 'list':
                flags |= os.O_DIRECTORY
            if operation=='write':
                flags = os.O_WRONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                effects.stage = 'write_open'
                try:
                    fd = os.open(name,flags|os.O_CREAT|os.O_EXCL,0o600,dir_fd=parent)
                except FileExistsError:
                    fd = os.open(name,flags,dir_fd=parent)
                else:
                    effects.changed('write_file_created')
            else:
                fd = os.open(name,flags,dir_fd=parent)
            try:
                if operation=='write':
                    effects.stage = 'write_descriptor_check'
                info = os.fstat(fd)
                if operation == 'list':
                    return self._list(fd)
                else:
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise Blocked('FS-LINK', 'Only an ordinary file with one link is allowed.')
                    if operation == 'write':
                        # Truncate only after verifying the opened descriptor.
                        effects.stage = 'write_truncate'
                        os.ftruncate(fd, 0)
                        effects.changed('write_data')
                        with os.fdopen(os.dup(fd), 'wb') as stream:
                            stream.write(action.data['content'].encode())
                            stream.flush()
                            effects.stage = 'write_data_fsync'
                            os.fsync(stream.fileno())
                        effects.changed('write_completed','applied')
                        output = 'Wrote file.'
                    else:
                        raw = self.read_bytes(fd)
                        output = raw.decode('utf-8',errors='replace')
                        metadata = {'sha256':hashlib.sha256(raw).hexdigest(),'total_lines':len(output.splitlines())}
                        if 'start_line' in action.data:
                            output = ''.join(output.splitlines(keepends=True)[action.data['start_line']-1:action.data['end_line']])
                        return {'exit_code':0,'stdout':output,'stderr':'',**metadata}
                return {'exit_code':0, 'stdout':output, 'stderr':'',**effects.result()}
            finally:
                os.close(fd)
