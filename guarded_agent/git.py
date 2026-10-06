import configparser
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from .domain import Action, MAX_GIT_METADATA_OUTPUT, MAX_GIT_PATHS
from .filesystem import Blocked, classify_parts
from . import sandbox

BRANCH = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_/-]{0,127}$')
REMOTE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')

def resolve_executable(executable):
    path = Path(executable)
    if not path.is_absolute():
        raise ValueError('Git executable must be an absolute trusted program.')
    path = path.resolve()
    if str(path)=='/usr/bin/git' and sys.platform=='darwin':
        # Apple's launcher writes a per-user xcrun cache outside private TMPDIR.
        # Resolve the selected developer Git once in the trusted operator host.
        selected = subprocess.check_output(['/usr/bin/xcrun','--find','git'],text=True,timeout=5).strip()
        path = Path(selected).resolve()
    if not path.is_absolute() or not path.is_file():
        raise ValueError('Git executable must be an existing absolute trusted program.')
    return str(path)

class Git:
    def __init__(self, filesystem, executable, remotes, trusted):
        self.fs = filesystem
        self.executable = str(Path(executable).resolve())
        self.remotes, self.trusted = remotes, trusted

    def _config_check(self):
        gitdir = self.fs.root / '.git'
        if not gitdir.is_dir() or gitdir.is_symlink():
            raise Blocked('GT-REPOSITORY', 'Only an ordinary .git directory at the workspace root is supported.')
        if (gitdir/'commondir').exists():
            raise Blocked('GT-REPOSITORY', 'Linked Git worktrees are unsupported in this release.')
        config_file = gitdir/'config'
        if config_file.is_symlink() or config_file.stat().st_nlink != 1 or config_file.stat().st_size>64_000:
            raise Blocked('GT-CONFIG', 'Git config must be a bounded ordinary file.')
        config = configparser.ConfigParser(interpolation=None, strict=True)
        try:
            config.read(config_file)
        except configparser.Error:
            raise Blocked('GT-CONFIG', 'Git config cannot be parsed safely.')
        allowed = {'core':{'repositoryformatversion','filemode','bare','logallrefupdates','ignorecase','precomposeunicode'},
                   'user':{'name','email'}}
        for section in config.sections():
            keys = set(config[section])
            if section in allowed and keys <= allowed[section]:
                if section=='core' and config[section].get('bare','false')!='false':
                    raise Blocked('GT-REPOSITORY','Expected a non-bare development repository.')
                continue
            if re.fullmatch(r'remote "[A-Za-z0-9_-]+"', section) and keys <= {'url','fetch'}:
                continue
            if re.fullmatch(r'branch "[A-Za-z0-9_/-]+"', section) and keys <= {'remote','merge'}:
                continue
            raise Blocked('GT-CONFIG', 'Repository config contains unapproved executable or external settings.')
        # Attribute filters and links are checked in one workspace traversal by
        # Gateway before normalization and again immediately before execution.

    def _argv(self, *args):
        return [self.executable, '-c','core.hooksPath=/dev/null', '-c','core.fsmonitor=false',
                '-c','core.pager=cat', '-c','commit.gpgsign=false', '-c','tag.gpgsign=false',
                '-c','user.name=User X', '-c','user.email=user-x@example.invalid',
                '-c','protocol.ext.allow=never', '-c','protocol.file.allow=always',
                '--no-pager', '--literal-pathspecs', *args]

    def _query(self, *args, strip=True, output_limit=None):
        # Queries are also sandboxed; malicious repository settings are checked before them.
        kwargs={'git':True,'trusted':self.trusted}
        if output_limit is not None:
            kwargs['output_limit']=output_limit
        result = sandbox.run(self._argv(*args), self.fs.root, self.fs.root, **kwargs)
        if result.get('output_truncated'):
            raise Blocked('GT-STATE','Repository state query exceeded the output bound; no action can be validated from incomplete state.')
        if result['exit_code']:
            raise Blocked('GT-STATE', 'Cannot resolve repository state: '+result['stderr'][:200])
        return result['stdout'].strip() if strip else result['stdout']

    def _state_paths(self, *args):
        # -z preserves whitespace and quotes in actual filenames. Never validate
        # a prefix of a truncated list, an unterminated record, or a filename
        # whose bytes were replaced during subprocess output decoding.
        raw = self._query(*args, strip=False, output_limit=MAX_GIT_METADATA_OUTPUT)
        if not raw:
            return []
        if not raw.endswith('\0'):
            raise Blocked('GT-STATE', 'Repository path query is not NUL terminated.')
        paths = raw[:-1].split('\0')
        if len(paths)>MAX_GIT_PATHS:
            raise Blocked('GT-STATE', 'Repository path query exceeded the bounded path count; no action can be validated from incomplete state.')
        for path in paths:
            self._validate_state_path(path)
        return paths

    @staticmethod
    def _validate_state_path(path):
        """Validate Git's slash-separated metadata lexically without per-path syscalls.

        The full workspace integrity scan immediately before normalization and
        the repeated scan before execution provide the symlink/hardlink checks.
        Git's NUL-delimited index output is already rooted in this repository;
        here we reject absolute, non-canonical, traversal, sensitive, and
        protected names while avoiding thousands of redundant Path.resolve,
        lstat, and stat calls for ordinary tracked files.
        """
        try:
            path_size = len(path.encode('utf-8'))
            candidate = PurePosixPath(path)
        except (UnicodeError, TypeError):
            raise Blocked('GT-STATE', 'Repository path query contains an unsupported filename.')
        if (not path or '\ufffd' in path or path_size>4096 or candidate.is_absolute()
                or candidate.as_posix()!=path or not candidate.parts
                or any(part in ('.','..') for part in candidate.parts)):
            raise Blocked('GT-STATE', 'Repository path query contains a non-canonical filename.')
        classify_parts(candidate.parts)

    def _explicit_paths(self, raw_paths, known_paths):
        paths = [self.fs.relative(path) for path in raw_paths]
        for path in paths:
            target = self.fs.root/path
            if path=='.' or target.is_dir() or any(p.startswith(path+'/') for p in known_paths):
                raise Blocked('GT-PATHS', 'Git paths must name explicit files, not directories.')
            if not target.is_file() and path not in known_paths:
                raise Blocked('GT-PATHS', 'Git paths must name existing or tracked files.')
        return paths

    def normalize(self, request):
        self._config_check()
        op = request['operation']
        tracked = self._state_paths('ls-files','-z')
        if op=='status':
            data = {'args':['status','--short']}
        elif op=='log':
            data = {'args':['log','-10','--oneline']}
        elif op in ('add','diff'):
            paths = [self.fs.relative(p) for p in request.get('paths',[])]
            options = ['--no-ext-diff','--no-textconv','--no-renames'] if op=='diff' else []
            if op=='diff' and request.get('staged',False):
                options.insert(0,'--cached')
            if op=='diff':
                # The index alone omits staged deletions and old rename paths.
                # Query every content source before rendering a patch; rendering
                # uses the same no-renames scope, including when HEAD is unborn.
                # Validate the whole changed set before applying a caller's file
                # filter, so selecting only a rename's new name cannot hide its
                # sensitive old source. This matches the whole-index guard above.
                sources = self._state_paths('diff',*options,'--name-only','-z','--')
                paths = self._explicit_paths(paths, tracked+sources)
                data = {'args':[op,*options,'--',*paths], 'source_paths':sources}
            else:
                paths = self._explicit_paths(paths, tracked)
                data = {'args':[op,'--',*paths]}
        elif op=='commit':
            message = request['message']
            if not message.strip():
                raise Blocked('GT-ARGS', 'Commit message must not be empty.')
            data = {'args':['commit','-m',message]}
        elif op=='branch':
            branch = request['name']
            self._branch(branch)
            data = {'args':['checkout','-b',branch]}
        elif op=='push':
            if request.get('force',False):
                raise Blocked('GT-DESTRUCTIVE','Force pushes are outside the capability.')
            branch, remote = request['branch'], request['remote']
            self._branch(branch)
            if branch in ('main','master'):
                raise Blocked('GT-DESTRUCTIVE','Direct pushes to protected branches are unavailable.')
            if not REMOTE.fullmatch(remote) or remote not in self.remotes:
                raise Blocked('GT-REMOTE','Remote is not in the operator profile.')
            url = self._query('remote','get-url','--push',remote)
            configured_url = url
            if Path(url).is_absolute():
                url = str(Path(url).resolve(strict=True))
            if url != self.remotes[remote]:
                raise Blocked('GT-REMOTE','Remote URL differs from the operator profile.')
            current = self._query('symbolic-ref','--short','HEAD')
            if current != branch:
                raise Blocked('GT-STATE','Push branch must be the current branch.')
            head = self._query('rev-parse','HEAD')
            local = Path(url)
            if local.is_absolute():
                target = str(local.resolve(strict=True))
                if str(local) != target or local.is_symlink() or not (local/'HEAD').is_file():
                    raise Blocked('GT-REMOTE','Local remote must be an ordinary canonical bare repository.')
                # An approved local remote must not be the workspace or trusted guard state.
                if local == self.fs.root or self.fs.root in local.parents or any(
                        local==Path(t) or Path(t) in local.parents for t in self.trusted):
                    raise Blocked('GT-REMOTE','Remote overlaps a protected location.')
                info=local.stat()
                remote_identity=[info.st_dev,info.st_ino]
            elif re.fullmatch(r'https://[A-Za-z0-9.-]+(?::[0-9]+)?/[A-Za-z0-9_./-]+',url):
                target = None
                remote_identity = None
            else:
                raise Blocked('GT-REMOTE','Only canonical local paths and credential-free HTTPS remotes are supported.')
            data = {'args':['push','--',url, head+':refs/heads/'+branch],
                    'remote':remote, 'url':url, 'configured_url':configured_url, 'branch':branch, 'head':head,
                    'remote_path':target, 'remote_identity':remote_identity, 'network':target is None,
                    'force':False}
        else:
            raise Blocked('CORE-UNKNOWN','Unknown Git operation.')
        return Action('git',op,data)

    @staticmethod
    def _branch(branch):
        if not BRANCH.fullmatch(branch) or branch.endswith('/') or '//' in branch:
            raise Blocked('GT-ARGS','Branch has unsupported syntax.')

    def _execute(self, action):
        self._config_check()
        # Close the last configuration/link check immediately before invoking Git.
        self.fs.check_workspace_links(reject_gitattributes=True)
        return sandbox.run(self._argv(*action.data['args']), self.fs.root, self.fs.root,
                           git=True, remote_path=action.data.get('remote_path'),
                           network=action.data.get('network',False), trusted=self.trusted)
