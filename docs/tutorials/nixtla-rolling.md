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
