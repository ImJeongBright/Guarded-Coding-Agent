import json
from pathlib import Path
import uuid
import time
from .domain import Action, Decision, Verdict, digest, validate
from .filesystem import Filesystem, Blocked, classify_parts
from .shell import Shell, validate_profile
from .git import Git, resolve_executable
from .approval import Approvals
from .audit import Audit, redact
from .sandbox import SandboxUnavailable
from .execution import ExecutionFailure
from .policy import evaluate

class Gateway:
    def __init__(self, workspace, state, policy=None, *, policy_path=None, run_id=None, actor='coding-agent'):
        self.workspace = Path(workspace).resolve(strict=True)
        self.state = Path(state).resolve()
        if self.state==self.workspace or self.workspace in self.state.parents:
            raise ValueError('Guard state must be outside the agent workspace.')
        self.policy_path = Path(policy_path).resolve() if policy_path else None
        if self.policy_path and (self.policy_path==self.workspace or self.workspace in self.policy_path.parents):
            raise ValueError('Policy file must be outside the agent workspace.')
        if policy_path:
            if Path(policy_path).is_symlink():
                raise ValueError('Policy cannot be a symlink.')
            policy = json.loads(self.policy_path.read_text())
        self.policy = json.loads(json.dumps(policy or {'version':'001','commands':[],'git_remotes':{},'approval_ttl':300}))
        self.source_digest = digest(self.policy)
        self._validate_policy()
        self.policy_digest = digest(self.policy)
        self.run_id = run_id or uuid.uuid4().hex
        self.actor = actor
        self.execution_block = None
        # Protect the executing package; sibling example workspaces remain usable.
        source = Path(__file__).resolve().parent
        self.trusted = [self.state, source, source.parent/'scripts', source.parent/'pyproject.toml']
        if self.policy_path:
            self.trusted.append(self.policy_path)
        self.approvals = Approvals(self.state)
        self.audit = Audit(self.state/'audit.jsonl')
        self.fs = Filesystem(self.workspace, self.trusted)
        self.shell = Shell(self.fs, self.policy.get('commands',[]),self.trusted)
        self.git = Git(self.fs, self.policy.get('git_executable','/usr/bin/git'),
                       self.policy.get('git_remotes',{}),self.trusted)

    def _validate_policy(self):
        policy = self.policy
        if not isinstance(policy,dict) or not isinstance(policy.get('version'),str):
            raise ValueError('Policy needs a string version.')
        ttl = policy.get('approval_ttl',300)
        if type(ttl) not in (int,float) or not 0 < ttl <= 3600:
            raise ValueError('Approval TTL must be between 0 and 3600 seconds.')
        if not isinstance(policy.get('git_remotes',{}),dict):
            raise ValueError('Invalid remote profile.')
        policy['git_executable'] = resolve_executable(policy.get('git_executable','/usr/bin/git'))
        for name, url in policy.get('git_remotes',{}).items():
            if not isinstance(name,str) or not isinstance(url,str):
                raise ValueError('Remote names and URLs must be strings.')
            if Path(url).is_absolute():
                policy['git_remotes'][name]=str(Path(url).resolve())
        commands = policy.get('commands',[])
        if not isinstance(commands,list) or len(commands)>64:
            raise ValueError('Commands must be a bounded list.')
        ids = set()
        for command in commands:
            argv = command['argv']
            validate({'tool':'shell','operation':'exec','argv':argv,'cwd':command.get('cwd','.')})
            validate_profile(command)
            if 'id' in command:
                if command['id'] in ids: raise ValueError('Profile ids must be unique.')
                ids.add(command['id'])
            executable = Path(argv[0])
            inside = executable.resolve()==self.workspace or self.workspace in executable.resolve().parents
            if not executable.is_absolute() or (not executable.is_file() and not inside):
                raise ValueError('Command executable must be absolute and exist, or be a declared workspace build output.')
            if self.workspace==executable.resolve() or self.workspace in executable.resolve().parents:
                # Workspace-produced binaries are reviewed capabilities, isolated at execution.
                pass
            command['executable'] = str(executable.resolve())
            writes=command.get('write_paths',[])
            if not isinstance(writes,list) or len(writes)>32:
                raise ValueError('write_paths must be a bounded list of relative workspace paths.')
            for raw in writes:
                if not isinstance(raw,str) or not raw or len(raw)>4096:
                    raise ValueError('Invalid command write path.')
                path=Path(raw)
                classify_parts(path.parts)
                if path.is_absolute() or '..' in path.parts or str(path)=='.':
                    raise ValueError('Command writes require a narrow relative path, not the entire workspace.')
                (self.workspace/path).resolve().relative_to(self.workspace)
            if type(command.get('timeout',20)) not in (int,float) or not 0<command.get('timeout',20)<=120:
                raise ValueError('Command timeout must be bounded.')

    def _binding(self, action):
        return {'action':action.payload(), 'workspace':str(self.workspace),
                'workspace_identity':self.fs.identity, 'run_id':self.run_id, 'actor':self.actor,
                'policy_version':self.policy['version'],'policy_digest':self.policy_digest}

    def _normalize(self, request, metrics=None):
        started = time.perf_counter()
        try:
            adapter, action = self._prepare(request)
        finally:
            if metrics is not None: metrics['normalization'] += (time.perf_counter()-started)*1000
        started = time.perf_counter()
        try:
            verdict = evaluate(action)
        finally:
            if metrics is not None: metrics['decision'] += (time.perf_counter()-started)*1000
        return adapter, action, verdict

    def _prepare(self, request):
        if self.execution_block:
            raise Blocked('SH-LIFECYCLE','A previous command could not be contained; restart only after operator recovery. '+self.execution_block)
        if self.policy_path and digest(json.loads(self.policy_path.read_text())) != self.source_digest:
            raise Blocked('AP-BINDING','Policy changed; restart the session with the new profile.')
        adapter = {'filesystem':self.fs,'shell':self.shell,'git':self.git}[request['tool']]
        if request['tool'] in ('shell','git'):
            self._check_links(include_attributes=request['tool']=='git')
        action = adapter.normalize(request)
        return adapter, action

    def _check_links(self, *, include_attributes=False):
        # Combine link and Git-attribute discovery in one full-tree pass.
        self.fs.check_workspace_links(reject_gitattributes=include_attributes)

    def submit(self, request, *, approval_id=None):
        metrics = dict(normalization=0.0,decision=0.0,audit=0.0,execution=0.0)
        started = time.perf_counter()
        result = self._submit(request,approval_id=approval_id,metrics=metrics)
        metrics['total'] = (time.perf_counter()-started)*1000
        metrics['other'] = max(0.0,metrics['total']-sum(v for k,v in metrics.items() if k!='total'))
        result['timings_ms'] = metrics
        return result

    def _submit(self, request, *, approval_id, metrics):
        def record(event):
            started = time.perf_counter()
            try: return self.audit.record(event)
            finally: metrics['audit'] += (time.perf_counter()-started)*1000
        action = None
        adapter = None
        try:
            request = validate(request)
            adapter, action, verdict = self._normalize(request,metrics)
        except Exception as error:
            verdict = Verdict(Decision.DENY,getattr(error,'rule','CORE-SCHEMA'),str(error))
        event = {'phase':'decision','run_id':self.run_id,'actor':self.actor,
                 'policy_version':self.policy['version'], 'policy_digest':self.policy_digest,
                 'action':redact(action.payload()) if action else {'invalid':True},
                 'decision':verdict.decision.value, 'matched_rule':verdict.rule,'reason':verdict.reason,
                 'approval_id':approval_id}
        result = {'decision':verdict.decision.value, 'matched_rule':verdict.rule, 'reason':verdict.reason,
                  'executed':False,'execution_status':'not_started','effect_status':'none',
                  'exit_code':None,'stdout':'','stderr':'','run_id':self.run_id}
        try:
            event_id = record(event)
        except OSError:
            return {**result,'decision':'DENY','matched_rule':'AU-ERROR','reason':'Audit unavailable; action was not executed.'}
        result['audit_event_id'] = event_id
        if verdict.decision==Decision.DENY:
            return redact(result)
        if verdict.decision==Decision.APPROVAL and approval_id is None:
            try:
                binding=self._binding(action)
                review={**action.payload(),'context':{k:v for k,v in binding.items() if k!='action'}}
                pending = self.approvals.pending(binding,redact(review),self.policy.get('approval_ttl',300))
                result['approval_id']=pending
                record({**event,'phase':'approval_pending','parent':event_id,'approval_id':pending})
            except Exception as error:
                result.update(decision='DENY',matched_rule='AP-INVALID',reason=str(error))
            return redact(result)
        try:
            _, rechecked, _ = self._normalize(request,metrics)
            if digest(rechecked.payload()) != digest(action.payload()):
                raise Blocked('AP-BINDING','Action or repository state changed before execution.')
            if approval_id is not None:
                if verdict.decision!=Decision.APPROVAL or not self.approvals.consume(approval_id,self._binding(rechecked)):
                    raise Blocked('AP-INVALID','Approval is ungranted, changed, expired, belongs to another session, or was consumed.')
            started = time.perf_counter()
            try: execution = adapter._execute(rechecked)
            finally: metrics['execution'] += (time.perf_counter()-started)*1000
            result.update(execution,executed=True)
            result.setdefault('execution_stage','completed')
            result['execution_status'] = 'succeeded' if result.get('exit_code')==0 else 'failed'
        except ExecutionFailure as error:
            result.update(error.result())
            if error.rule=='SH-LIFECYCLE':
                self.execution_block = str(error)
            if not error.executed:
                result.update(decision='DENY',matched_rule=error.rule,reason=str(error))
        except Exception as error:
            result.update(decision='DENY',matched_rule=getattr(error,'rule','SH-SANDBOX' if isinstance(error,SandboxUnavailable) else 'EXEC-ERROR'), reason=str(error))
        try:
            record({**event,'phase':'result','parent':event_id,'result':result,'timings_ms':dict(metrics)})
        except OSError:
            result['audit_error']='Execution finished but result audit could not be persisted.'
        return redact(result)
