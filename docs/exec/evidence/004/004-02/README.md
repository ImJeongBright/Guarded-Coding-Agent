# 004-02 workspace scan evidence

- `measurement-summary.json` contains three-call M1/M2 Gateway medians, maxima and per-call integrity scan counts/timing.
- `scan-comparison.json` compares the previous five traversals (two link walks plus three attributes walks) with three combined traversals, repeated three times per fixture.
- M1/M2 include captured Guard audit logs and reconstructed normalized policies. Policy digests were checked against audit decisions.
- `regression.json` and `regression.log` show the 166-test suite passed with no failures, errors or skips. The shell wrapper had a post-test zsh variable error; see the Exec record.
- `regression/test_workspace_scan.py`, `measure.py` and `compare_scan.py` preserve the reproducible test/measurement logic.
- `pre-change/004-01-summary.json` preserves the earlier one-call capacity sample; it is not a repeated benchmark.
- `source-delta.json` records source hashes changed or added since the 004-01 manifest.

`$RUN`, `$REPO` and `$HOME` replace local paths. `export-manifest.json` records original and portable hashes. Path-transformed result/audit/policy files are review artifacts and cannot replace raw files for session revalidation. Raw fixture repositories, audit and measurements remain in `.guard-runs/scale-probe-02/` and `.guard-runs/scale-probe-03/`.
