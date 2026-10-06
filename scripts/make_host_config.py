"""Generate a reviewable local Codex config; never modify global config."""
import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from guarded_agent.host import configuration, toml_value

parser = argparse.ArgumentParser()
parser.add_argument('--workspace', required=True)
parser.add_argument('--state', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args()
work = Path(args.workspace).resolve(strict=True)
output = Path(args.output).resolve()
if output == work or work in output.parents:
    parser.error('Host config must be outside the agent workspace.')
config = configuration(work, args.state)
text = '# Dedicated guarded Codex profile. Review /hooks before activation.\n'
text += '\n'.join(key+' = '+toml_value(value) for key, value in config.items())+'\n'
fd = os.open(output, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
with os.fdopen(fd, 'w') as stream:
    stream.write(text)
print(output)
