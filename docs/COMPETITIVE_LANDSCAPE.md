# Competitive landscape and build decision

**Reviewed:** 2026-08-30

## Executive conclusion

ForecastGuard should remain a specialized trust gate, not become another data
schema framework or forecasting library. Adjacent tools cover pieces of the
workflow, but none of the reviewed products combines a Nixtla-native
rolling-origin contract, fitted-feature availability evidence, behavioural
feature/prediction perturbation, and a CI-blocking typed report.

## Closest adjacent tools

| Tool | What it does well | Overlap | Gap ForecastGuard fills |
|---|---|---|---|
| [MLForecast cross-validation](https://nixtlaverse.nixtla.io/mlforecast/docs/how-to-guides/cross_validation.html) | Produces rolling-origin forecasts with `cutoff` metadata | Generates the evidence being checked | Does not independently gate malformed windows or perturb the pipeline for leakage |
| [sktime `evaluate`](https://www.sktime.net/docs/api-reference/sktimeforecastingmodel-evaluationevaluate/) | Evaluates forecasters over temporal resampling strategies | Rolling/backtest execution | Evaluation framework, not a forecast-specific data/availability/leakage CI contract |
| [Deepchecks train/test validation](https://docs.deepchecks.com/stable/tabular/auto_checks/train_test_validation/index.html) | Generic tabular train/test overlap, drift, and index/date leakage checks | Leakage-adjacent validation | Not Nixtla/rolling-origin aware; does not rerun feature or forecast callables under unavailable-future interventions |
| [Great Expectations](https://docs.greatexpectations.io/docs/core/define_expectations/) | Reusable declarative assertions and validation results | Columns, nulls, uniqueness, CI validation | Users must author generic expectations; no forecasting-window semantics or behavioural model sensitivity |
| [Pandera](https://pandera.readthedocs.io/en/stable/dataframe_schemas.html) | Typed dataframe schemas, column/index checks, custom checks | Input schema and dataframe constraints | No built-in forecast-origin, point-in-time availability, fitted-consumption, or perturbation contract |

These tools are complements. A team can validate dataframe types with Pandera or
Great Expectations, create backtests with MLForecast or sktime, and place
ForecastGuard immediately before model selection to decide whether that
backtest is trustworthy.

## Defensible differentiation

1. **Behavioural proof at two boundaries.** Feature outputs before an origin and
   predictions after it are diffed under contract-aware interventions.
2. **Forecast-native windows.** `cutoff`, rolling `cutoffs`, and Nixtla
   `cutoff_col` are explicit, mutually exclusive input shapes with exact grids.
3. **Availability tied to actual consumption.** Point-in-time timestamps and an
   optional fitted MLForecast adapter close the gap between declarations and
   features the model consumes.
4. **CI is the product.** Stable violation codes, loud skips, one versioned
   report, non-zero exit semantics, SARIF, GitHub annotations, and Action
   artifacts are first-class rather than notebook-only diagnostics.
5. **Honest claims.** A failure establishes sensitivity; a pass is bounded to
   tested windows, data, modes, and tolerance.

## Features deliberately not added

- Generic dataframe schema authoring: use Pandera or Great Expectations.
- Forecast model training, tuning, or scoring: use Nixtla, sktime, Darts, etc.
- Drift/production monitoring: adjacent observability products already own it.
- A Polars backend: the measured pandas path is currently above the documented
  50k rows/s decision threshold.
- More registered checks: the public architecture remains three narrow checks;
  new evidence is composed inside those contracts.

## What should happen next

Publish the current release candidate, collect real failing pipelines, and rank
new work by observed false negatives and integration demand. The most plausible
follow-ons are StatsForecast/sktime adapters, selective suppressions with expiry
and ownership, and an irregular-series contract—but none should be implemented
without user evidence.
