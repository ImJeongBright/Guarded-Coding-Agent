# 004-05 live M1/M2 evidence

This folder contains portable copies from five planned live Codex development tasks and one post-optimization follow-up, all run through the local Guard MCP server. Raw workspaces, full-resolution sessions and original audit files remain in `.guard-runs/scale-probe-03/`.

- `session-summary.json` records each isolated task, start/end revision, exact changed paths, full-test count, Guard decisions, incomplete searches, duration, commit and independent verification result.
- `sessions/M1-task-*` and `sessions/M2-task-*` include the path-scrubbed Codex events, prompts, host preflight/invocation, session boundary records, and independent verifier report.
- `patches/` contains each task commit patch from its disposable workspace.
- `fixtures/` and `host-state/` contain the scale counts, safe profile and cumulative Guard decision/result audits. Host authentication databases and logs are not included.
- `latency-M1.json` and `latency-M2.json` summarize the five planned sessions before the Git metadata fast path. `latency-post-optimization-live.json` reports the sixth task after the change.
- `post-optimization-benchmark.json` contains six read-only Guard Git `status` calls per profile after the optimization; `post-optimization-audit/` contains the corresponding audit.
- `setup-observation.json` records the first M2 baseline `FS-LINK` denial and its successful integrity scan/build/test retry.
- `regression-focused.json` records the five Git metadata tests; `regression-final.json` records the full 173-test suite.
- `source-manifest-before.json`, `source-manifest.json`, and `source-delta.json` compare code against the 004-04 source manifest. The only changed source/test files are `guarded_agent/git.py` and `tests/test_scale_git_metadata.py`.
- `export-manifest.json` records original and portable SHA-256 values for converted copies.

`$RUN`, `$REPO`, and `$HOME` replace machine-specific paths in exported content. Event and audit JSON is path-transformed for review, so it cannot be used instead of the originals to rerun `validate_session`. The tracked original `examples/c-dbms` was not an agent workspace; M1/M2 were disposable functional multi-module C DBMS copies with synthetic file-volume fixtures.

## Measurements

Before the change, M2 path metadata validation spent 4.26 seconds inside 10,000 calls to `Filesystem.relative()`. After switching Git-produced NUL paths to strict lexical parsing, a six-call `git status` median fell from 3.90 to 1.11 seconds on M2, while the three complete workspace scans and final executor-boundary scan remained active. The following actual Codex task measured status/diff/add/commit at roughly 1.0–1.3 seconds.

One M2 root guidance search still returned the explicit 5,000-entry `entry_limit` incomplete marker. The agent narrowed the scope, and later searches completed. This evidence supports a short-run usability judgment for this macOS profile; it does not measure long-term human satisfaction.
