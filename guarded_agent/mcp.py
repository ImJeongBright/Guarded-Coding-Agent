"""Minimal local stdio MCP transport, protocol 2025-11-25 family."""
import json
from .domain import SCHEMA, MAX_CONTENT
from .audit import redact

TOOLS = {'guard_filesystem':'filesystem','guard_shell':'shell','guard_git':'git'}

def descriptors(gateway=None):
    result=[]
    for name, tool in TOOLS.items():
        variants=[]
        for (surface,operation),(required,optional) in SCHEMA.items():
            if surface!=tool:
                continue
            properties={'operation':{'const':operation,'type':'string'}}
            for field in required|optional:
                if field in ('argv','paths'):
                    properties[field]={'type':'array','items':{'type':'string'},'minItems':1,'maxItems':128}
                elif field=='exclude_dirs':
                    properties[field]={'type':'array','items':{'type':'string'},'minItems':0,'maxItems':32}
                elif field in ('force','staged'):
                    properties[field]={'type':'boolean'}
                elif field in ('start_line','end_line'):
                    properties[field]={'type':'integer','minimum':1,'maximum':1_000_000}
                else:
                    properties[field]={'type':'string'}
            if tool=='git':
                properties['approval_id']={'type':'string'}
            variants.append({'type':'object','properties':properties,'required':['operation',*sorted(required)],'additionalProperties':False})
        description=f'Guarded local {tool} operations. DENY returns a reason; push pauses for an operator approval. No agent approval tool exists.'
        if gateway is not None and tool=='shell':
            profiles=[{k:v for k,v in command.items() if k in ('id','argv','cwd','timeout','write_paths','variants','filter')} for command in gateway.policy.get('commands',[])]
            description += ' Use run with profile=id, optional mode=variant name and filter=literal test-name text; or exact registered argv/cwd with exec. Profiles: '+json.dumps(redact(profiles),ensure_ascii=False)
        if tool=='filesystem':
            description += ' read optionally takes start_line/end_line (at most 500 lines) and returns full-file sha256. search is literal bounded text search; query="" lists ordinary file paths matching glob without reading content. search can take up to 32 exact exclude_dirs relative to its path to skip known generated directories; exclusions do not use .gitignore pattern rules. edit replaces one unique old_text with new_text only when expected_sha256 matches the full file; use sha256 from read or the previous successful edit.'
        if gateway is not None and tool=='git':
            description += ' Approved remote names: '+json.dumps(list(gateway.policy.get('git_remotes',{})))+'. Stage explicit file paths. Push current feature branch only.'
        result.append({'name':name,'description':description,
                       'inputSchema':{'type':'object','oneOf':variants}})
    return result

class Server:
    def __init__(self,gateway):
        self.gateway=gateway
        self.initialized=False
        self.ready=False

    def dispatch(self,message):
        request_id=message.get('id') if isinstance(message,dict) else None
        def error(code,text):
            return {'jsonrpc':'2.0','id':request_id,'error':{'code':code,'message':text}}
        if not isinstance(message,dict) or message.get('jsonrpc')!='2.0' or not isinstance(message.get('method'),str):
            return error(-32600,'Invalid request')
        method=message['method']
        if 'id' not in message:
            if method=='notifications/initialized' and self.initialized:
                self.ready=True
            return None
        params=message.get('params',{})
        if not isinstance(params,dict):
            return error(-32602,'Parameters must be an object')
        if method=='initialize':
            version=params.get('protocolVersion')
            if version not in ('2024-11-05','2025-03-26','2025-06-18','2025-11-25'):
                version='2025-11-25'
            self.initialized=True
            result={'protocolVersion':version,'capabilities':{'tools':{}},
                    'serverInfo':{'name':'guarded-coding-agent','version':'0.1.0'},
                    'instructions':'Use only guard tools for filesystem/shell/git. Operator approves pending pushes in a separate terminal. Run: '+self.gateway.run_id}
        elif method=='ping':
            result={}
        elif method not in ('tools/list','tools/call'):
            # Modern clients probe server/discover before falling back to initialize.
            # Report an unsupported method rather than an initialization-state error.
            return error(-32601,'Method not found')
        elif not self.ready:
            return error(-32000,'Initialize and send notifications/initialized first')
        elif method=='tools/list':
            result={'tools':descriptors(self.gateway)}
        elif method=='tools/call':
            name=params.get('name')
            if name not in TOOLS:
                return error(-32602,'Unknown tool')
            arguments=params.get('arguments',{})
            if not isinstance(arguments,dict) or 'tool' in arguments:
                return error(-32602,'Invalid tool arguments')
            arguments=dict(arguments)
            approval_id=arguments.pop('approval_id',None)
            if approval_id is not None and not isinstance(approval_id,str):
                return error(-32602,'Invalid approval identifier')
            outcome=self.gateway.submit({'tool':TOOLS[name],**arguments},approval_id=approval_id)
            result={'content':[{'type':'text','text':json.dumps(outcome,ensure_ascii=False)}],
                    'structuredContent':outcome,'isError':outcome['decision']=='DENY' or outcome['exit_code'] not in (None,0) or outcome.get('execution_status')=='failed'}
        else:
            return error(-32601,'Method not found')
        return {'jsonrpc':'2.0','id':request_id,'result':result}

    def serve(self,input_stream,output_stream):
        while True:
            line=input_stream.readline(MAX_CONTENT*2+1)
            if not line:
                break
            if len(line)>MAX_CONTENT*2:
                # Drain this one oversized frame without retaining it.
                while line and not line.endswith('\n'):
                    line=input_stream.readline(MAX_CONTENT*2+1)
                response={'jsonrpc':'2.0','id':None,'error':{'code':-32600,'message':'Frame too large'}}
            else:
                try:
                    response=self.dispatch(json.loads(line))
                except (ValueError,TypeError,RecursionError):
                    response={'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'Invalid JSON'}}
            if response is not None:
                output_stream.write(json.dumps(response,ensure_ascii=False)+'\n')
                output_stream.flush()
