# P2 — Forecast-level behavioural perturbation

**Date:** 2026-08-30

**Status:** Complete

**Goal:** Detect leakage that bypasses a standalone feature function, including
direct use of unavailable exogenous values and teacher forcing within a horizon.

## Contract

`forecast_fn` is an optional `"module:callable"` accepting two independent
dataframes, `(train_df, future_df)`, and returning a dataframe with the declared
id/time columns plus one or more prediction columns.

For every raw-data cutoff ForecastGuard:

1. runs the callable twice on full inputs to establish determinism;
2. censors target and past-only future inputs while preserving declared
   future/static inputs;
3. reruns the callable for each configured deterministic perturbation mode;
4. aligns predictions by `(id, ds)` and diffs model outputs.

An observed prediction change is `FG-FORECAST-001`. Missing prerequisites,
nondeterminism, exceptions, or unalignable outputs skip loudly. CV-output-only
frames cannot supply training history and therefore skip this component.

## Acceptance

- A clean recursive forecast passes.
- Direct actual-weather use and holdout target teacher forcing fail.
- Declared planned inputs do not fail.
- Multi-window evidence includes cutoff, perturbation, prediction column, and
  changed-row samples.
- Feature-level and forecast-level outcomes aggregate without hiding skips.
