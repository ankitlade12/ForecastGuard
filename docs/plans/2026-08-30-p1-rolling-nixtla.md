# P1 — Rolling-origin Nixtla contract

> Historical implementation record. Status and verification below are as of this
> plan's date; see the [current roadmap](../../ROADMAP.md) and [plan index](README.md).

**Date:** 2026-08-30

**Status:** Complete

**Goal:** Validate the rolling-origin backtests ForecastGuard is positioned to
protect, and close the gap between declared future availability and the raw
features an MLForecast model actually consumes.

## Contract

`ForecastSpec` supports exactly one window source:

- `cutoff`: legacy single holdout; all rows after the cutoff are the holdout.
- `cutoffs`: rolling-origin raw-history mode; each holdout is bounded to the
  configured horizon and later history is allowed.
- `cutoff_col`: Nixtla CV-output mode; cutoffs are read from the frame and each
  `(series, cutoff)` holdout grid is validated.

Multi-window violations carry the cutoff in structured evidence and location.
Legacy single-window codes and locations remain backward compatible.

An optional MLForecast adapter loads or builds a fitted forecaster, intersects
`ts.features_order_` with raw input covariates, and adds that consumed-feature
metadata to `CheckContext`. The known-future check fails when a raw exogenous
feature consumed by MLForecast is neither future-known nor static.

## Acceptance

- Rolling raw history allows observations beyond an earlier window while still
  detecting missing/misaligned points inside every horizon.
- Nixtla CV output validates `(id, cutoff, ds)` uniqueness and exact grids.
- Cutoff, future-coverage, and runtime evidence identify the affected window.
- A fake adapter contract test and a real optional MLForecast integration test
  verify consumed exogenous feature discovery.
- A runnable Nixtla tutorial demonstrates raw-history and CV-output validation.
