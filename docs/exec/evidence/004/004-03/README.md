# 004-03 search exclusion evidence

- `search-measurement.json` records three calls per operation for M1/M2, with decisions, incomplete reasons, match paths and latency.
- M1/M2 contain actual Guard audit logs and reconstructed policies. The recorded policy digest matches each decision audit.
- `regression-004-03.json` and its log record the 170-test suite with zero failures/errors/skips.
- `regression/` preserves the generated-tree exclusion tests and MCP schema assertion.
- `source-delta.json` compares source hashes with the completed 004-02 manifest.

`$RUN`, `$REPO` and `$HOME` replace local paths. `export-manifest.json` contains raw and portable hashes. Transformed evidence is for review and cannot replace raw artifacts for revalidation. Original workspace fixtures, audit and measurements are in `.guard-runs/scale-probe-02/` and `.guard-runs/scale-probe-03/`.
