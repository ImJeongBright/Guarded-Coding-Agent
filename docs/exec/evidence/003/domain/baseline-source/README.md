# MONEY PILOT Domain

This package contains deterministic financial-simulation and decision-feedback
rules. It has no HTTP, database, provider-key, browser, or deployment-platform
dependency. Amounts use the existing MVP unit of 만 원.

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
