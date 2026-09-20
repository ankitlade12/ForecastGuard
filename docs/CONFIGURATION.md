# Configuration reference

[Documentation home](README.md) · [CLI reference](CLI.md) · [Examples](../examples/README.md)

ForecastGuard loads a YAML mapping into `ForecastSpec`. Unknown fields and invalid
role/window combinations are rejected. Data, revision and model paths resolve
relative to the YAML file. Quote date values so YAML preserves them as strings.

## A complete example

The following spec is equivalent to the bundled clean replay configuration when
saved beside `examples/adoption/data.csv` and `pipelines.py`:

```yaml
name: demand-validation
data: data.csv
id_col: unique_id
time_col: ds
target_col: y
cutoffs: ['2024-01-04', '2024-01-06']
horizon: 2
freq: D
future_covariates: []
static_covariates: []
pipeline_factory: 'pipelines:clean_factory'
perturbations: [nullify, noise, sign_flip]
max_probe_calls: 10
```

## Dataset and windows

| Field | Default / requirement | Meaning |
|---|---|---|
| `name` | Optional | Label included in reports |
| `data` | Required in YAML; optional with Python `frame` | CSV or Parquet path; Parquet needs the `parquet` extra |
| `id_col`, `time_col`, `target_col` | `unique_id`, `ds`, `y` | Series identifier, event timestamp and target |
| `horizon` | Required positive integer | Number of future periods to validate |
| `freq` | Required | pandas frequency such as `D`, `MS` or `W-MON` |
| `cutoff` | One window source required | Single boundary; all later rows must match the horizon |
| `cutoffs` | Alternative to `cutoff` | Raw-history origins; each horizon is bounded independently |
| `cutoff_col` | Alternative to both | Origin column in a materialized CV output |

Specify exactly one of `cutoff`, nonempty `cutoffs`, or `cutoff_col`.
CV rows are scoring outputs; they do not provide raw history for runtime probes.

## Availability and revisions

| Field | Default | Meaning |
|---|---|---|
| `future_covariates` | `[]` | Inputs explicitly known at prediction time |
| `static_covariates` | `[]` | Inputs invariant within each series |
| `availability` | `[]` | `covariate` / `available_at_col` declarations for future inputs |
| `revisions` | `[]` | Sidecar histories with `column`, `data`, `value_col`, `available_at_col`, `policy` |

Unlisted covariates are treated as past-only. The future target is never a
known-future input. Calendar variables or planned promotions may qualify as
future-known; observed weather does not become known merely because it is present
in a historical table. Static and future roles cannot overlap or use reserved keys.

Availability timestamps must satisfy the implemented event-time and origin-time
checks. Revision fields default to `value_col: value`,
`available_at_col: available_at`, `policy: latest_available`. This policy also
rejects stale-but-previously-available values. See
[historical revision validation](ADOPTION_GUIDE.md#5-historical-revision-validation).

## Runtime interfaces

References use `package.module:callable`. The CLI adds the YAML directory and
working directory to the import path. In Python API usage, make the modules
importable yourself.

| Field | Signature | Return value |
|---|---|---|
| `feature_fn` | `build_features(frame)` | DataFrame with id/time keys and computed feature columns |
| `forecast_fn` | `predict(train, future)` | DataFrame with id/time keys and numeric prediction columns |
| `pipeline_factory` | `create_pipeline()` | Fresh object with `predict(frame, cutoff, spec)` returning predictions |

You can configure feature and forecast functions together. A pipeline factory
is mutually exclusive with either. All are optional for structural validation;
without an executable interface, runtime validation skips.

Features must have unique, aligned id/time keys and comparable pre-cutoff output.
Predictions must cover the complete horizon for all series, with finite numeric
baseline values. Return prediction columns rather than a scoring table containing
actual future targets. Outputs must be deterministic under repeated identical inputs.

Forecast functions receive historical `train` and a horizon `future` frame.
Future contains scoring targets and undeclared inputs so the guard can perturb
them; your prediction code must select only legitimate known inputs. Factories
receive raw history plus the current horizon. Put preprocessing and fitting
inside `predict` to include them in replay. See the
[fresh replay contract](ADOPTION_GUIDE.md#4-fresh-pipeline-replay).

## Probes and diagnostics

| Field | Default | Meaning |
|---|---|---|
| `perturbations` | `[nullify]` | Nonempty unique selection of `nullify`, `noise`, `sign_flip` |
| `perturbation_seed` | `0` | Seed for repeatable noise |
| `max_probe_calls` | Unset | Total runtime execution cap; zero disables configured probes with a skip |
| `diagnostics` | `false` | Run explanatory single-input interventions after a behavioural failure |
| `max_diagnostic_calls` | `20` | Diagnostic cap, also constrained by remaining total calls |

Generated specs explicitly select all three modes. Handwritten specs retain the
single-mode default. Primary calls are `origins × components × (2 + modes)`;
each component runs twice to check determinism. Diagnostics spend additional
calls from the remaining budget. Numeric comparisons use `rtol=1e-5`, `atol=1e-8`.
Call caps are not timeouts. See [planning and coverage](ADOPTION_GUIDE.md#2-execution-planning-and-coverage).

## Optional fitted-model inspection

```yaml
adapter:
  kind: mlforecast
  model_fn: 'myproject.models:build_fitted'
```

`model_fn(frame)` must return a fitted MLForecast object. Alternatively specify
`model_path` pointing to an MLForecast saved model. Exactly one source is required.
This is distinct from the unfitted `--model-factory` used by `init`.

Inspection checks consumed raw covariates against declarations. Adapter
loading/fitting is outside the runtime probe count. Only load trusted code and
model artifacts; see [SECURITY.md](../SECURITY.md).

## Python API

For DataFrames and callable objects without YAML, use the
[Python API guide](PYTHON_API.md). `ForecastSpec.data` may be omitted when you
pass `frame` to `forecastguard.run_checks`; YAML specs still require `data`.
The existing file-based interface remains available:

```python
from forecastguard.config import load_spec
from forecastguard.planning import plan_execution
from forecastguard.runner import run_checks

spec = load_spec('examples/adoption/replay-clean.yaml')
spec = spec.model_copy(update={
    'pipeline_factory': 'examples.adoption.pipelines:clean_factory'
})
plan = plan_execution(spec)
print(plan.model_dump_json(indent=2))
report = run_checks(spec)
print(report.model_dump_json(indent=2))
raise SystemExit(report.exit_code(strict=True))
```

This example runs from the repository root and replaces the CLI's sibling-module
reference with an importable package reference. For your own code, install your
pipeline as an importable package.
`load_spec` and data loading can raise configuration/IO errors; individual check
exceptions are represented as ERROR results by the runner.
