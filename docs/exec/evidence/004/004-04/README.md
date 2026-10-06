# 004-04 build-limit evidence

- `build-limits.json` records the actual guarded C compile/run and the 100 KB output, 33 MiB file and timeout probes.
- `normalized-policy.json` was reconstructed; its digest matches the final run's decisions in `audit-final-run.jsonl`.
- `audit-full.jsonl` also retains the first SDK-less exploratory build attempt, which used a different policy digest and exited unsuccessfully.
- `regression.json` and `regression.log` preserve the 171-test run; `regression/test_sandbox_edges.py` contains the new file-size control.
- `source-delta.json` compares code/test hashes with the 004-03 manifest.

`$RUN`, `$REPO` and `$HOME` replace local paths. The export manifest keeps raw/portable file hashes. Transformed artifacts are review copies; raw C source, binary, partial oversized file and audit remain in `.guard-runs/scale-probe-03/build-scope/`.
