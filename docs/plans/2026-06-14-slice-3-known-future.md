# Slice 3 — Known-future covariates

**Date:** 2026-06-14
**Status:** Delivered
**Goal:** Implement the declared-vs-used contract diff for future covariates —
deterministic and zero-false-positive.

## Delivered

- `KnownFutureCovariatesCheck` (replaces the Slice-1 stub) in
  [`forecastguard/checks/known_future.py`](../../forecastguard/checks/known_future.py).
  Validates `spec.future_covariates` against the data; surfaces undeclared
  covariates as "past-only". Semantics in DECISIONS **D-012**.
- 8 unit tests in
  [`tests/unit/test_known_future.py`](../../tests/unit/test_known_future.py) —
  clean, missing-column, empty-in-holdout, undeclared-not-a-failure, static
  excluded, multi-violation, custom column names.
- [`examples/known_future/{clean,broken}`](../../examples/known_future/) — PASS
  vs. a 2-violation FAIL, with a README.

## Why a contract check (D-012)

From a historical panel you can't tell a future covariate from a past one (both
have post-cutoff values), so inferring leakage from the data would false-positive
on every legitimate past covariate. Slice 3 therefore validates the *declared*
contract; the behavioural proof of leakage is the runtime check (Slice 4).

## Violations

- `FG-FUTURE-001` (HIGH) — declared future covariate is not a column.
- `FG-FUTURE-002` (HIGH) — declared future covariate has no values anywhere in the
  holdout window.

## Verification (met)

- `pytest` 43/43; `ruff` + `ruff format --check` + `mypy --strict` green.
- CLI: clean example exits `0`; broken example exits `1` (`FG-FUTURE-001` +
  `FG-FUTURE-002`). Quickstart still exits `0` (cutoff + known-future PASS;
  runtime SKIP).

## Next

- **Slice 4** — Runtime leakage (behavioural perturbation, D-003) + the headline
  leaky→clean demo (PRD §5 wedge). This is the one check that needs `feature_fn`.
