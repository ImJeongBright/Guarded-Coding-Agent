import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

class MCPTests(unittest.TestCase):
    def test_stdio_agent_surface_and_error_recovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary); work=base/'work'; work.mkdir(); state=base/'state'
            state.mkdir(); profile=state/'policy.json'; profile.write_text('{"version":"001","commands":[]}')
            requests=[
                {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'X','version':'1'}}},
                {'jsonrpc':'2.0','method':'notifications/initialized'},
                {'jsonrpc':'2.0','id':2,'method':'tools/list'},
                {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'guard_filesystem','arguments':{'operation':'write','path':'a.c','content':'int a;'}}},
                {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'approve','arguments':{}}},
                {'jsonrpc':'2.0','id':5,'method':'tools/call','params':{'name':'guard_filesystem','arguments':{'operation':'read','path':'a.c'}}},
            ]
            data='\n'.join(json.dumps(x) for x in requests)+'\n'
            result=subprocess.run([sys.executable,'-m','guarded_agent','serve','--workspace',str(work),'--state',str(state),'--policy',str(profile)],input=data,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            responses=[json.loads(x) for x in result.stdout.splitlines()]
            self.assertEqual(len(responses),5)
            self.assertEqual(responses[0]['result']['protocolVersion'],'2025-11-25')
            names={x['name'] for x in responses[1]['result']['tools']}
            self.assertEqual(names,{'guard_filesystem','guard_shell','guard_git'})
            shell=next(x for x in responses[1]['result']['tools'] if x['name']=='guard_shell')
            self.assertIn('exact registered argv/cwd',shell['description'])
            self.assertTrue(responses[2]['result']['structuredContent']['executed'])
            self.assertIn('error',responses[3])
            self.assertEqual(responses[4]['result']['structuredContent']['stdout'],'int a;')

if __name__=='__main__':
    unittest.main()
