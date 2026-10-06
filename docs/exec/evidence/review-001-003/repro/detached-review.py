"""Bounded child-lifetime reproduction; only disposable workspace writes."""
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent/'guarded_agent/gateway.py').is_file())
RUN = ROOT/'.guard-runs/review-001-003'
RUN.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))
from guarded_agent.gateway import Gateway

records = {}
with tempfile.TemporaryDirectory(prefix='guard-review-detached-') as raw:
    base = Path(raw).resolve(); work = base/'work'; work.mkdir(); (work/'output').mkdir()
    marker = work/'output/late-marker'
    child = 'from pathlib import Path; import time; time.sleep(0.3); Path("output/late-marker").write_text("fixture-only")'
    for label, tail, timeout in [('normal_return','',1), ('timeout','; import time; time.sleep(1)',0.1)]:
        marker.unlink(missing_ok=True)
        source = f'import subprocess,sys; p=subprocess.Popen([sys.executable,"-c",{child!r}],start_new_session=True); print(p.pid,flush=True)'+tail
        argv = [str(Path(sys.executable).resolve()), '-B', '-c', source]
        guard = Gateway(work, base/('state-'+label), {'version':'review-detached',
            'commands':[{'argv':argv, 'write_paths':['output'], 'timeout':timeout}]})
        result = guard.submit(dict(tool='shell', operation='exec', argv=argv))
        immediate = marker.exists()
        time.sleep(0.7)
        late = marker.exists()
        record = {key:result.get(key) for key in ('decision','matched_rule','executed','exit_code','stdout','stderr','timed_out')}
        record.update(marker_on_return=immediate, marker_later=late)
        assert not immediate and late, record
        if label == 'timeout': assert result['timed_out'] and result['exit_code'] == 124, result
        records[label] = record
    (ROOT/'.guard-runs/review-001-003/detached-results.json').write_text(json.dumps(records, indent=2)+'\n')
    print(json.dumps(records, indent=2))
