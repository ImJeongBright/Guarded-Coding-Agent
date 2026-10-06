"""Repeat representative M1/M2 calls and account for integrity traversals."""
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

PYTHON = str(Path(sys.executable).resolve())

def run_case(name, target, repeats=3):
    fixture = ROOT/'.guard-runs'/'scale-probe-02'/name
    work = fixture/'workspace'
    argv = [PYTHON, '-B', '-c', 'print("guard-medium-ok")']
    gateway = Gateway(work, BASE/(name+'-state'), {
        'version':'scale-post-004-02',
        'commands':[{'argv':argv}],
        'git_remotes':{},
    })
    original_scan = gateway.fs.check_workspace_links
    scan_ms = []

    def measured_scan(*args, **kwargs):
        started = time.perf_counter()
        try:
            return original_scan(*args, **kwargs)
        finally:
            scan_ms.append((time.perf_counter()-started)*1000)

    gateway.fs.check_workspace_links = measured_scan
    calls = {}
    requests = {
        'git_status':{'tool':'git','operation':'status'},
        'single_file_diff':{'tool':'git','operation':'diff','paths':[target]},
        'shell_noop':{'tool':'shell','operation':'exec','argv':argv},
    }
    for label, request in requests.items():
        samples = []
        decisions = []
        rules = []
        scan_counts = []
        scan_times = []
        for _ in range(repeats):
            before_scans = len(scan_ms)
            started = time.perf_counter()
            result = gateway.submit(request)
            samples.append(round((time.perf_counter()-started)*1000, 3))
            decisions.append(result['decision'])
            rules.append(result['matched_rule'])
            scan_counts.append(len(scan_ms)-before_scans)
            scan_times.append(round(sum(scan_ms[before_scans:]), 3))
        calls[label] = {
            'samples_ms':samples,
            'median_ms':round(statistics.median(samples), 3),
            'max_ms':max(samples),
            'decisions':decisions,
            'rules':rules,
            'workspace_scan_count_per_call':scan_counts,
            'workspace_scan_total_ms_per_call':scan_times,
        }
    record = {
        'fixture':name,
        'tracked_files':3000 if name.startswith('M1') else 10000,
        'ignored_build_files':10000 if name.startswith('M1') else 25000,
        'fixture_root':str(work),
        'repeats_per_operation':repeats,
        'platform':platform.platform(),
        'python':platform.python_version(),
        'calls':calls,
    }
    (BASE/(name+'-measurement.json')).write_text(json.dumps(record, indent=2)+'\n')
    return record

results = [
    run_case('M1-3000-10000', 'src/module_029/component_02999.c'),
    run_case('M2-10000-25000', 'src/module_099/component_09999.c'),
]
(BASE/'measurement-summary.json').write_text(json.dumps({
    'kind':'post-004-02 repeated synthetic capacity measurement',
    'fixture_only':True,
    'calls_per_operation':3,
    'results':results,
}, indent=2)+'\n')
for result in results:
    print(json.dumps({
        'fixture':result['fixture'],
        'calls':{label:{'median_ms':call['median_ms'],'max_ms':call['max_ms'],
            'scan_count':call['workspace_scan_count_per_call'],
            'scan_ms':call['workspace_scan_total_ms_per_call'],
            'decisions':call['decisions']} for label,call in result['calls'].items()},
    }), flush=True)
