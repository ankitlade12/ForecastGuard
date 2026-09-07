# Validate MLForecast rolling-origin backtests

ForecastGuard accepts both the raw history used to create rolling windows and
MLForecast's materialized `cross_validation` output. The runnable fixtures are
in [`examples/nixtla_rolling`](../../examples/nixtla_rolling/).

## 1. Validate raw history across multiple origins

```bash
forecastguard run --spec examples/nixtla_rolling/raw.yaml
```

`cutoffs` bounds each window to exactly `horizon` points. Observations after an
earlier window remain valid history for later origins.

## 2. Validate Nixtla cross-validation output

MLForecast emits `unique_id`, `ds`, `cutoff`, `y`, and prediction columns. Point
ForecastGuard at the `cutoff` metadata column:

```bash
forecastguard run --spec examples/nixtla_rolling/cv.yaml
```

ForecastGuard validates unique `(unique_id, cutoff, ds)` keys and the exact
horizon grid for every `(series, cutoff)` pair. Runtime perturbation skips
loudly in this mode because a CV output contains no raw pre-cutoff history.

To regenerate the fixture with MLForecast:

```bash
uv sync --extra nixtla
uv run --extra nixtla python examples/nixtla_rolling/mlforecast_tutorial.py
```

## 3. Inspect the fitted model's raw exogenous inputs

The optional adapter checks what the fitted model actually consumes, rather
than trusting declarations alone:

```yaml
adapter:
  kind: mlforecast
  model_fn: "mlforecast_tutorial:build_fitted"
```

The runner intersects `model.ts.features_order_` with raw dataframe columns. A
consumed raw feature that is neither `future_covariates` nor
`static_covariates` fails as `FG-FUTURE-004`. Install adapter support with
`pip install 'forecastguard[nixtla]'`.

MLForecast documentation: [cross-validation](https://nixtlaverse.nixtla.io/mlforecast/docs/how-to-guides/cross_validation.html),
[exogenous features](https://nixtlaverse.nixtla.io/mlforecast/docs/how-to-guides/exogenous_features.html).

## 4. Replay the existing forecast function

`mlforecast_tutorial.forecast(train, future)` reuses `build_fitted` and projects
the future frame to the known inputs passed to `MLForecast.predict`. Use the
same callable for your ordinary backtest and ForecastGuard. It must return only
the id/time keys and prediction columns, not a scoring table containing actuals.

```bash
uv sync --extra dev --extra nixtla
uv run --extra nixtla forecastguard run --spec examples/nixtla_rolling/runtime.yaml --strict
uv run --extra nixtla python -m benchmarks.integration_benchmark
```

The added YAML selects two existing origins, the callable, one perturbation, and
`max_probe_calls: 6`. Integration requires a small `(train, future) -> predictions`
wrapper if your pipeline does not already expose that interface. The existing
CSV-only specs need no pipeline code changes, but provide no runtime assurance.

Runtime cost is at most `origins × configured callables × (2 + modes)` user
calls. The two baseline calls test determinism. A callable that fits a model
will fit it on each execution. `max_probe_calls` rejects an oversized plan before
runtime imports/calls; it does not silently sample windows. Choose explicit
`cutoffs` and `perturbations` to reduce work. Omission means no call-count cap;
zero disables configured runtime probes with a loud SKIP. The budget excludes
optional adapter loading/fitting and is not a wall-clock timeout.

The integration benchmark uses synthetic demand for 20 series over 120 days,
real MLForecast/LinearRegression, two origins and seven-day horizons. It compares
the existing two-call backtest with six additional guard calls, and verifies
that replacing forecasts with actual targets fails. It reports median timings
over five runs and Python allocation peaks from a separate tracemalloc run
(not total RSS). This is an adoption/cost example, not a research benchmark.

Run the gate after pipeline changes and before trusting model-selection scores.
If retraining is expensive, run basic validation on every change and explicitly
budget runtime probes on representative origins. Frozen pretrained models,
external caches, inaccurate availability declarations and untested origins can
hide dependencies the configured probes cannot establish.
