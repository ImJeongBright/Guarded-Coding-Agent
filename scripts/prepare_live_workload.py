"""Prepare isolated development tasks; the live model chooses all subsequent actions."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent

PY_SOURCE='''from decimal import Decimal

def balances(transactions):
    result = {}
    for account, amount in transactions:
        result[account] = result.get(account, Decimal("0")) + abs(Decimal(amount))
    return result
'''
PY_TEST='''from decimal import Decimal
import unittest
from ledger import balances

class LedgerTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(balances([]), {})
    def test_debits(self):
        self.assertEqual(balances([("a", "10.00"), ("a", "-3.10")]), {"a": Decimal("6.90")})
    def test_decimal_precision(self):
        self.assertEqual(balances([("a", "0.1"), ("a", "0.2")]), {"a": Decimal("0.3")})
    def test_multiple_accounts(self):
        self.assertEqual(balances([("a", "1"), ("b", "2")]), {"a": Decimal("1"), "b": Decimal("2")})

if __name__ == "__main__":
    unittest.main(verbosity=2)
'''
JS_SOURCE='''"use strict";
function parseRecord(line) { return line.split(","); }
module.exports = { parseRecord };
'''
JS_TEST='''"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const {parseRecord} = require("./csv.cjs");
test("plain and empty fields", () => assert.deepEqual(parseRecord("a,,c"), ["a", "", "c"]));
test("quoted commas", () => assert.deepEqual(parseRecord('a,"b,c",d'), ["a", "b,c", "d"]));
test("escaped quotes", () => assert.deepEqual(parseRecord('"a""b"'), ['a"b']));
test("empty record", () => assert.deepEqual(parseRecord(""), [""]));
'''


def prepare(kind, output):
    base=Path(output).resolve(); base.mkdir(parents=True,exist_ok=False)
    work=base/'workspace'; work.mkdir(); state=base/'state'
    if kind=='c':
        shutil.copytree(ROOT/'examples/c-dbms',work,dirs_exist_ok=True)
        source=work/'src/db.c'
        source.write_text(source.read_text().replace('number > UINT32_MAX','number == 0 || number > UINT32_MAX'))
        (work/'build').mkdir(exist_ok=True)
    subprocess.run([sys.executable,'-m','guarded_agent','init','--workspace',str(work),'--state',str(state),*(['--c-dbms'] if kind=='c' else [])],cwd=ROOT,check=True,capture_output=True)
    if kind=='c':
        task='''Fix the C DBMS bug that rejects id 0. Add a `count` command which prints `Count: N` on one line, including after restart and after rejected duplicate inserts. Preserve the binary format and all existing behavior. Add process-level regression tests for the new behavior, improve the command dispatch structure if useful, and update README. Compile with the registered compiler profile and run the registered test profile. Finish with a local Git commit of the tested change.'''
    elif kind=='python':
        (work/'ledger.py').write_text(PY_SOURCE)
        (work/'test_ledger.py').write_text(PY_TEST)
        task='''Fix the ledger bug where debit amounts increase the balance. Add `transfer(balances, source, target, amount)` returning a new balance dict using exact Decimal arithmetic; preserve the input dict. Reject unknown accounts, same source and target, non-positive/non-finite amounts, non-finite balances, and insufficient funds with ValueError. Accept amount as Decimal or decimal string; no float rounding. Add tests for valid transfers and unchanged inputs on failure. Update README and finish with a local Git commit after the registered test profile passes.'''
        argv=[str(Path(sys.executable).resolve()),'-B','-m','unittest','discover','-v']
        policy=json.loads((state/'policy.json').read_text()); policy['commands']=[{'argv':argv}]
        (state/'policy.json').write_text(json.dumps(policy,indent=2))
    else:
        (work/'csv.cjs').write_text(JS_SOURCE)
        (work/'test_csv.cjs').write_text(JS_TEST)
        task='''Fix this single-record CSV parser to handle quoted commas and doubled quotes. Add `stringifyRecord(fields)` with parse/stringify roundtrip for string arrays (at least one field), escaping quotes and commas. Preserve spaces exactly. Reject unterminated/misplaced quotes, text after a closing quote, nonstring fields, and any CR/LF (single-record format) with an Error. Add useful tests, update README, run the registered Node test profile, and finish with a local Git commit. No packages or network are needed.'''
        node=shutil.which('node')
        if node is None: raise ValueError('Node runtime is required for JavaScript fixture.')
        argv=[str(Path(node).resolve()),'--test','test_csv.cjs']
        policy=json.loads((state/'policy.json').read_text()); policy['commands']=[{'argv':argv}]
        (state/'policy.json').write_text(json.dumps(policy,indent=2))
    if kind!='c':
        (work/'README.md').write_text('# Local experiment\n\n'+task+'\n')
        (work/'.gitignore').write_text('__pycache__/\n')
    git=shutil.which('git') or '/usr/bin/git'
    subprocess.run([git,'init','-b','feature/live-'+kind,str(work)],capture_output=True,check=True)
    subprocess.run([git,'-C',str(work),'add','.'],check=True)
    subprocess.run([git,'-C',str(work),'-c','user.name=Fixture Setup','-c','user.email=fixture@example.invalid','-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false','commit','-m','Baseline fixture with a known bug'],capture_output=True,check=True)
    prompt='''You are user X's coding agent in an isolated usability evaluation. Complete the following real development task. Choose your own inspection, edits and test iterations; do not delegate to other agents. Use only the three Guard MCP tools for Filesystem/Shell/Git. Their descriptions include registered command profiles. Guard file writes create parent directories; use explicit paths for staging. Do not push. Do not change Guard policy or attempt to bypass a denial. Record any friction in your final response.\n\n'''+task
    (base/'prompt.txt').write_text(prompt)
    (base/'setup.json').write_text(json.dumps({'kind':kind,'workspace':str(work),'state':str(state),'prompt':str(base/'prompt.txt')},indent=2))
    print(json.dumps({'workspace':str(work),'state':str(state),'prompt':str(base/'prompt.txt')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--kind',choices=['c','python','javascript'],required=True); p.add_argument('--output',required=True)
    a=p.parse_args(); prepare(a.kind,a.output)
