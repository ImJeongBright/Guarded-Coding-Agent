# MONEY PILOT Domain

This package contains deterministic financial-simulation and decision-feedback
rules. It has no HTTP, database, provider-key, browser, or deployment-platform
dependency. Amounts use the existing MVP unit of 만 원.

## Decision input validation

`evaluateDecision` requires `openedSources` to be a nonnegative safe integer
(from 0 through `Number.MAX_SAFE_INTEGER`). Invalid values throw `RangeError`
before feedback processing begins. Valid-input scoring is unchanged: opened
sources contribute 8 evidence points each, with total evidence capped at 30.

## Regression validation

Run the suite with `npm test` on Node >=22.13.0. Tests use Node's built-in
test runner and strict assertions, with no added dependencies or random seeds.
The `decision regression:` tests cover source-count boundaries (0 through
MAX_SAFE_INTEGER), malformed runtime counts, adjacent finite values around
both direction thresholds, and unavailable/non-finite actual changes.
Thresholds are inclusive flat bands: ±0.05 for ordinary assets and ±1 for
10Y yields. Unknown changes produce null actual/correct results and withhold
prediction points.

A fixed 23,040-case matrix checks deterministic feedback, finite scores in
0..100, component totals, the reachable 100-point cap, and unchanged inputs
(including frozen nested prediction/change records). Rejected counts also
leave inputs unchanged.

## Provenance

The baseline was copied read-only from the external competition frontend at
Git revision bb444c79d87a03863a04c34491c668cd1ac7e133. No files were written
in that repository.

| Source file | SHA-256 |
| --- | --- |
| lib/simulation.ts | 3d793ae1e0713ee20f55e76702e011ba0d93d5cd7b913ba12866826011e07a28 |
| lib/decision-feedback.ts | 04431844bce51e5af0e2e920e9b96d88a128179e1704e2df3543730dded14050 |
| lib/annual-scenario.ts | 5dc0dd83b86106217839c170aee19cac9c794147ccd3ef315bc51e2f953b9637 |
| tests/simulation.test.mjs | 47a4b4d92c393393eefa1754eb65b0e6671ff8562fb6996e221a0221b9af0d9b |

The copied test suite intentionally excludes UI/article-content assertions;
those belong to the versioned scenario-data layer. It retains all simulation,
score, result-lock, and counterfactual checks.
