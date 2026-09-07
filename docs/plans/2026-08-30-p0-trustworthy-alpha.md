# P0 — Trustworthy public alpha

**Date:** 2026-08-30

**Status:** Delivered

**Goal:** Make the existing three-check product safe to publish and honest about
what a behavioural perturbation can establish.

## Scope

1. Reject null series identifiers instead of allowing pandas grouping to drop
   them and produce a false PASS.
2. Tighten the covariate contract:
   - reject conflicting column roles in `ForecastSpec`;
   - require declared static columns to exist and be time-invariant per series;
   - require declared future covariates to cover every available holdout row,
     with structured evidence for affected series.
3. Version the serialized `Report` contract and expose it through
   `forecastguard run --format json` without mixing human output into stdout.
4. Replace universal "leak-free" PASS language with bounded language: no
   future sensitivity was detected for the tested cutoff, mask, and tolerance.
5. Add an Apache-2.0 license and align the README, roadmap, decisions, and
   changelog with the release state.

## Explicitly deferred

- Publishing to PyPI, creating a Git tag/release, or changing GitHub repository
  visibility.
- Rolling-origin/multi-cutoff support.
- An MLForecast adapter and forecast-level perturbation.
- Alternative perturbation modes and Polars support.

## Acceptance

- The all-null-ID regression returns `FG-CUTOFF-014` and exits non-zero.
- Missing/varying static covariates and partial future coverage return typed,
  stable violations.
- Invalid role overlap is rejected by the typed spec boundary.
- JSON CLI output round-trips through `Report.model_validate_json` and preserves
  the normal exit-code semantics, including `--strict`.
- Existing examples retain their intended exit codes.
- pytest, coverage, ruff, mypy strict, package build, and clean-install smoke
  verification pass.
