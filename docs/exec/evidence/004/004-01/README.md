# 004-01 Git metadata evidence

- `summary.json` records M1/M2 synthetic sizes and one actual Guard call per listed operation.
- `regression-final.json` records the 162-test run; its complete console log is adjacent.
- M1/M2 contain actual Guard audit, normalized policy and result JSON. The policy digest was checked against the captured audit.
- `regression/test_scale_git_metadata.py` is the end-to-end large path/sensitive deletion regression source.
- `pre-change/scale-summary.json` keeps the preceding baseline sample visible.
- `source-delta.json` compares the current code and tests with the prior 52-file manifest.

`$RUN`, `$REPO` and `$HOME` replace local paths. `export-manifest.json` records both original and portable hashes.
Portable result/audit/policy copies are review artifacts; path transformation means they cannot replace the raw files for session revalidation.
Raw generated repositories, guard audit, and original unconverted results remain in `.guard-runs/scale-probe-02/`.
No model host log, local auth, external project, or external remote was used.
