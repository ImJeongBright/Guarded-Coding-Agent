# 005 evidence

2026-10-06. Current Guard finalization evidence. Historical 001–004 evidence is preserved unchanged. New runs use disposable state directories; the scale replay uses preserved 004 workspaces and policies without replacing their historical audit or verification.

- `baseline.json` / `.log`: first nested-sandbox baseline, 173 tests, 55 failures / 14 errors; execution backend unavailable.
- `baseline-host.json` / `.log`: same baseline on the host, 173 tests passed.
- `source-manifest-before.json`: source hashes at the start of finalization.
- `injection-initial.json`, `focused-red.log`: result audit failure originally returned MCP success and CLI exit 0; follow-up write proceeded after storage restoration.
- `injection-final.json`, `focused-green.log`: audit error is exposed, CLI/MCP fail and the same Gateway blocks further execution. Controller SIGKILL leaves a contained child; trusted operator fixture cleanup succeeds. This is not automatic recovery.
- `regression-{unit,adversarial,lifecycle,scale,full}.json` / `.log`: respectively 18 / 106 / 40 / 13 / 177 tests, all passed with no skips. Lifecycle/scale HEAD is `523b77c` with finalization source changes present; unit/adversarial/full HEAD is `0060a56`. Exact source SHA-256 values match across all five runs.
- `runtime-focused.log`: 10 runtime/Seatbelt tests passed, including read-only selected Python runtime with secret and adjacent external paths denied.
- `source-binding.json`: current 57 source hashes, group/hash equality, delta from 004-05, and the two replay script hashes.
- `scale-recheck-overlapping.json`: first replay while other regression work could affect timing; retained for comparison.
- `scale-recheck-serial.json`, `scale-audit/{M1,M2}.jsonl`: replay after regressions finished. Three Guard status samples per profile, build and 22 / 33 project tests, unchanged HEAD and clean ending status. Not a new model session or a long-term performance study.
- `cli-smoke-nested.json`, `cli-audit/nested.jsonl`: documented CLI flow stopped before build because nested Seatbelt application was denied.
- `cli-smoke-host.json`, `cli-audit/host.jsonl`: disposable operator CLI init/discover/profile-apply/config/build/test and pinned Codex preflight passed on the host; no model session.
- `repro/cli_smoke.py`, `repro/scale_recheck.py`: reproduction helpers; output must be a new directory. Shell/Git work requires a macOS host permitting Guard's Seatbelt backend.
- `export-manifest.json`: raw and portable SHA-256 values for newly exported evidence.

`$REPO`, `$HOME`, and `$TMP` replace machine-specific paths. These are review copies; path-bound digests remain the original values and cannot authenticate a replay at a substituted path. Source hashes use relative repository paths and remain verifiable. No authentication DB, global config, or approval DB is exported.

Commands:

```sh
python3 scripts/check.py --group full --evidence /tmp/guard-final-reproduce.json
python3 docs/exec/evidence/005/repro/cli_smoke.py --output /tmp/guard-cli-reproduce-new
python3 docs/exec/evidence/005/repro/scale_recheck.py \
  --m1 .guard-runs/scale-probe-03/live-M1/workspace \
  --m2 .guard-runs/scale-probe-03/live-M2/workspace \
  --output /tmp/guard-scale-reproduce-new
```

Raw scale workspaces are local operator artifacts, not included in this repository. Portable fixture/session/patch evidence is linked from [004-05](../004/004-05/README.md). Reproduction can use equivalent operator-prepared workspaces and adjacent `operator-state/policy.json`; it does not reconstruct model sessions from exported logs.
