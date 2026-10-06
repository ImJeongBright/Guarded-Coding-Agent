"""Run a dedicated guarded Codex evaluation/session without changing global settings."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from guarded_agent.host import capture, command, preflight
from scripts.session_evidence import start_session, finish_session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--state', required=True)
    parser.add_argument('--prompt-file', required=True)
    parser.add_argument('--output', required=True, help='New evidence directory outside workspace')
    parser.add_argument('--reviewed-hook', action='store_true',
                        help='Operator has reviewed scripts/codex_pre_tool.py; trust only this invocation')
    parser.add_argument('--timeout', type=int, default=900)
    args = parser.parse_args()
    work = Path(args.workspace).resolve(strict=True)
    output = Path(args.output).resolve()
    if output == work or work in output.parents:
        parser.error('Evidence must be outside the agent workspace.')
    checked = preflight(work, args.state)
    output.mkdir(parents=True, exist_ok=False)
    invocation = command(work, args.state, reviewed_hook=args.reviewed_hook)
    (output/'preflight.json').write_text(json.dumps(checked, indent=2))
    (output/'invocation.json').write_text(json.dumps(invocation, indent=2))
    prompt = Path(args.prompt_file).read_text()
    (output/'prompt.txt').write_text(prompt)
    baseline = start_session(work, args.state, output)
    code = capture(invocation, prompt, output, args.timeout)
    (output/'exit.json').write_text(json.dumps({'exit_code': code}))
    try:
        finish_session(work, args.state, output, baseline, code)
    except (OSError, ValueError) as error:
        # Preserve the failed run and its actual CLI exit, but never pass a run
        # whose ending revision/audit could not be recorded.
        (output/'session-evidence-error.json').write_text(json.dumps({'error':str(error)}))
        print(json.dumps({'exit_code':code, 'evidence':str(output), 'evidence_error':str(error)}))
        return code or 1
    print(json.dumps({'exit_code': code, 'evidence': str(output)}))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
