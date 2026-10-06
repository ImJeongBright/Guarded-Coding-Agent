"""Measure explicit generated-directory exclusion and module scoping on M1/M2."""
import json
import platform
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from guarded_agent.gateway import Gateway

def case(name, target, module, repeats=3):
    fixture = ROOT/'.guard-runs'/'scale-probe-02'/name
    work = fixture/'workspace'
    gateway = Gateway(work, BASE/(name+'-search-state'), {'version':'scale-search-004-03'})
    requests = {
        'root_without_exclusion':{'path':'.','query':'SCALE_POST_004','glob':'*.c'},
        'root_excluding_build':{'path':'.','query':'SCALE_POST_004','glob':'*.c','exclude_dirs':['build']},
        'target_module':{'path':module,'query':'SCALE_POST_004','glob':'*.c'},
    }
    calls = {}
    for label, fields in requests.items():
        samples = []
        outcomes = []
        for _ in range(repeats):
            started = time.perf_counter()
            result = gateway.submit({'tool':'filesystem','operation':'search',**fields})
            samples.append(round((time.perf_counter()-started)*1000, 3))
            outcomes.append({'decision':result['decision'],'incomplete':result.get('incomplete'),
                'reasons':result.get('truncation_reasons'), 'entries':result.get('scanned_entries'),
                'bytes':result.get('scanned_bytes'), 'matches':[m['path'] for m in result.get('matches',[])],
                'excluded_dirs':result.get('excluded_dirs')})
        calls[label] = {'samples_ms':samples,'median_ms':round(statistics.median(samples),3),
                        'max_ms':max(samples),'outcomes':outcomes}
    return {'fixture':name,'tracked_files':3000 if name.startswith('M1') else 10000,
            'ignored_files':10000 if name.startswith('M1') else 25000,
            'target':target,'module':module,'repeats_per_operation':repeats,
            'platform':platform.platform(),'python':platform.python_version(),'calls':calls}

results = [case('M1-3000-10000','src/module_029/component_02999.c','src/module_029'),
          case('M2-10000-25000','src/module_099/component_09999.c','src/module_099')]
record={'kind':'004-03 explicit search exclusion synthetic measurement','fixture_only':True,
        'results':results}
(BASE/'search-measurement.json').write_text(json.dumps(record,indent=2)+'\n')
for result in results:
    print(json.dumps({'fixture':result['fixture'],'calls':{
        name:{'median_ms':call['median_ms'],'incomplete':call['outcomes'][-1]['incomplete'],
              'reasons':call['outcomes'][-1]['reasons'],'matches':call['outcomes'][-1]['matches']}
        for name,call in result['calls'].items()}}),flush=True)
