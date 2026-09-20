# Slice 4 — Runtime leakage (the moat)

> Historical implementation record. Status and verification below are as of this
> plan's date; see the [current roadmap](../../ROADMAP.md) and [plan index](README.md).

**Date:** 2026-06-14
**Status:** Delivered
**Goal:** Implement behavioural-perturbation leakage detection — the
differentiating check — plus the headline leaky→clean demo.

## Delivered

- `RuntimeLeakageCheck` (replaces the Slice-1 stub) in
  [`forecastguard/checks/runtime_leak.py`](../../forecastguard/checks/runtime_leak.py):
  contract-aware future masking, a determinism probe, re-run + pre-cutoff diff,
  and `FG-LEAK-001` per leaking feature. Semantics in DECISIONS **D-013**.
- `feature_fn` resolution now adds the working directory (`runner`) and the spec
  file's directory (`cli`) to `sys.path`, so a feature module next to the spec
  imports.
- 10 unit tests in
  [`tests/unit/test_runtime_leak.py`](../../tests/unit/test_runtime_leak.py) —
  clean pass, centered-window leak, whole-series-mean leak, the zero-FP
  declared-future-covariate case (and its undeclared counterpart that *is*
  flagged), plus every loud-skip branch.
- The headline demo:
  [`examples/runtime_leakage/`](../../examples/runtime_leakage/) —
  `features.py` (clean + leaky), shared `data.csv`, `clean.yaml`, `leaky.yaml`,
  README.

## How it works (D-013)

Mask the future (NaN the target + past-only covariates; keep declared future +
static covariates), re-run `feature_fn`, diff pre-cutoff values. A trailing
feature is unchanged; a centered window or whole-series scaler moves. Numeric
diff via `np.isclose`. SKIPS loudly when it can't prove anything (no `feature_fn`,
nondeterministic, raises, unalignable output, no holdout).

## Verification (met)

- `pytest` 53/53; `ruff` + `ruff format --check` + `mypy --strict` green.
- CLI: `clean.yaml` → all three checks PASS, exit `0`; `leaky.yaml` → runtime
  FAIL (`centered_mean_3`, `y_vs_series_mean`; `lag_1` stays clean), exit `1`.
- All seven example specs across the four slices exit as designed.

## Milestone

**All three checks are now implemented.** The product described in the
ForecastGuard one-pager is functionally complete.

## Next

- **Slice 5 — Ship.** GitHub Action hardening, README GIF, a Nixtla
  `cross_validation` tutorial PR, first PyPI release, choose a license.
