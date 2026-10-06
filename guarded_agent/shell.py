from pathlib import Path
import re
from .domain import Action
from .filesystem import Blocked
from . import sandbox

PROFILE_ID = re.compile(r'^[a-z][a-z0-9-]{0,63}$')
FILTER_TEXT = re.compile(r'^[\w][\w .:-]{0,99}$',re.UNICODE)

def filtered_argv(command, argv, text):
    spec = command.get('filter')
    if spec is None or not FILTER_TEXT.fullmatch(text):
        raise Blocked('SH-FILTER','Use a literal test name (letters, numbers, spaces, underscore, dot, colon, hyphen; at most 100 characters).')
    option = ['-k',text] if spec['kind']=='python-unittest-literal' else ['--test-name-pattern',re.escape(text)]
    result = list(argv)
    result[spec['position']:spec['position']] = option
    return result

def validate_profile(command):
    if 'id' in command and (not isinstance(command['id'],str) or not PROFILE_ID.fullmatch(command['id'])):
        raise ValueError('Profile id must be a short lowercase name.')
    variants = command.get('variants',{})
    if not isinstance(variants,dict) or len(variants)>8:
        raise ValueError('At most eight named fixed argv variants are allowed.')
    from .domain import validate
    for name,argv in variants.items():
        if not isinstance(name,str) or not PROFILE_ID.fullmatch(name) or name=='default':
            raise ValueError('Invalid variant name.')
        validate({'tool':'shell','operation':'exec','argv':argv})
        if argv[0]!=command['argv'][0]:
            raise ValueError('Variants must use the same fixed executable.')
    spec = command.get('filter')
    if spec is not None:
        if not isinstance(spec,dict) or set(spec)!={'kind','position'} or spec['kind'] not in ('python-unittest-literal','node-test-literal'):
            raise ValueError('Unknown test filter configuration.')
        position = spec['position']
        if type(position) is not int or not 1<=position<=min(len(argv) for argv in [command['argv'],*variants.values()]):
            raise ValueError('Filter position must be inside the fixed argument list.')
        for argv in [command['argv'],*variants.values()]:
            if spec['kind']=='node-test-literal' and ('--test' not in argv or Path(argv[0]).name!='node'):
                raise ValueError('Node filters apply only to builtin Node test profiles.')
            if spec['kind']=='python-unittest-literal' and (not Path(argv[0]).name.startswith('python') or not any(p.endswith('.py') for p in argv[1:])):
                raise ValueError('Python filters apply only to reviewed unittest script profiles.')

class Shell:
    def __init__(self, filesystem, commands, trusted):
        self.fs, self.commands, self.trusted = filesystem, commands, trusted

    def normalize(self, request):
        if request['operation']=='run':
            command = next((c for c in self.commands if c.get('id')==request['profile']),None)
            if command is None:
                raise Blocked('SH-PROFILE','Unknown profile id; operator discovery/review is required.')
            mode = request.get('mode','default')
            if mode=='default':
                argv = list(command['argv'])
            elif mode in command.get('variants',{}):
                argv = list(command['variants'][mode])
            else:
                raise Blocked('SH-PROFILE','Unknown mode; use a named reviewed variant.')
            if 'filter' in request:
                argv = filtered_argv(command,argv,request['filter'])
            return self._action(command,argv,request.get('stdin',''))
        argv = request['argv']
        if Path(argv[0]).name in ('sh','bash','zsh','fish','env','sudo'):
            raise Blocked('SH-SYNTAX', 'Nested shells and environment wrappers are unavailable.')
        cwd = self.fs.relative(request.get('cwd','.'))
        for command in self.commands:
            if command.get('cwd','.')!=cwd: continue
            for fixed in [command['argv'],*command.get('variants',{}).values()]:
                if fixed==argv:
                    return self._action(command,argv,request.get('stdin',''))
                spec = command.get('filter')
                if spec is not None and len(argv)==len(fixed)+2:
                    position = spec['position']
                    flag = '-k' if spec['kind']=='python-unittest-literal' else '--test-name-pattern'
                    if argv[position]==flag and [*argv[:position],*argv[position+2:]]==fixed:
                        derived = filtered_argv(command,fixed,argv[position+1])
                        return self._action(command,derived,request.get('stdin',''))
        # A reviewed exact argument may contain punctuation as data. No shell parses it.
        if any(re.search(r'[;|<>`\n]|\$\(|&&', argument) for argument in argv):
            raise Blocked('SH-SYNTAX', 'Use separate structured tool calls; shell composition is unavailable.')
        raise Blocked('SH-PROFILE', 'Command argv/cwd is not in the operator profile. Use an approved command or ask the operator to add a narrow profile.')

    def _action(self, command, argv, stdin):
        if Path(argv[0]).name in ('sh','bash','zsh','fish','env','sudo'):
            raise Blocked('SH-SYNTAX','Nested shells and environment wrappers are unavailable.')
        if not Path(argv[0]).is_absolute() or str(Path(argv[0]).resolve())!=command['executable']:
            raise Blocked('SH-PROFILE','Executable identity does not match the trusted profile.')
        cwd = self.fs.relative(command.get('cwd','.'))
        return Action('shell','exec',{'argv':argv,'cwd':cwd,'stdin':stdin,
            'timeout':command.get('timeout',20),'write_paths':command.get('write_paths',[])})

    def _execute(self, action):
        data = action.data
        return sandbox.run(data['argv'], self.fs.root/data['cwd'], self.fs.root,
                           stdin=data['stdin'], timeout=data['timeout'], trusted=self.trusted,
                           write_paths=data['write_paths'])
