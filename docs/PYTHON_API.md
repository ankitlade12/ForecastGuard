# Python library

Import ForecastGuard in a notebook, training script, or model-selection pipeline.
Pass a pandas DataFrame and your actual Python functions to the same engine used
by the CLI and GitHub Action. No YAML or temporary CSV is needed.

## Install

From a source checkout, with Python 3.12 or 3.13:

```bash
python -m pip install .
# Optional real MLForecast integration:
python -m pip install '.[nixtla]'
```

The project is pre-release. These commands install the local package;
PyPI publication remains a separate maintainer step.

## Quickstart

```python
import pandas as pd
import forecastguard

frame = pd.DataFrame({
    "unique_id": ["A"] * 6,
    "ds": pd.date_range("2024-01-01", periods=6, freq="D"),
    "y": [1.0, 3.0, 2.0, 4.0, 6.0, 5.0],
})

def features(data):
    return data[["unique_id", "ds"]].assign(
        lag=data.groupby("unique_id")["y"].shift(1)
    )

spec = forecastguard.ForecastSpec(cutoff="2024-01-04", horizon=2, freq="D")
report = forecastguard.run_checks(spec, frame=frame, feature_fn=features)
assert report.exit_code(strict=True) == 0
```

Changing `shift(1)` to `shift(-1)` reads tomorrow's target. The runtime check
reports `FG-LEAK-001` and the strict exit code becomes `1`.

Functions can be local functions, closures, bound methods, or callable objects.
Put the preprocessing you want tested inside the function. Closures over cached
future values remain outside the interventions; a PASS only covers the supplied
data, boundaries, origins, perturbations and tolerance.

## Public entry point

```python
forecastguard.run_checks(
    spec,
    checks=None,
    *,
    frame=None,
    feature_fn=None,
    forecast_fn=None,
    pipeline_factory=None,
) -> forecastguard.Report
```

| Input | Contract |
|---|---|
| `spec` | `ForecastSpec`: column mappings, exactly one window source, horizon/frequency, covariate roles and execution settings |
| `frame` | pandas DataFrame; takes precedence over `spec.data`. When omitted, the runner loads the configured CSV/Parquet path |
| `feature_fn` | `(frame) -> DataFrame` containing identity/time columns and feature columns; compares rows before each origin |
| `forecast_fn` | `(train, future) -> DataFrame` containing identity/time columns and finite numeric predictions for the complete horizon |
| `pipeline_factory` | `() -> ReplayPipeline`, a fresh object implementing `predict(frame, cutoff, spec) -> DataFrame`; put preprocessing and fitting inside `predict` |
| `checks` | Advanced custom check sequence, with caller-managed ordering and prerequisites; omit to use the standard gate |

`ForecastSpec`, `Report`, `CheckResult`, `CheckStatus`, `Severity`, `Violation`,
`AvailabilitySpec`, `RevisionSpec`, `MLForecastAdapterSpec`, `ReplayPipeline`,
and `run_checks` are exported from `forecastguard`. Existing submodule imports
continue to work. Public types and keyword parameters are the supported library
surface; underscore-prefixed helpers are internal. This remains an alpha API;
pin the package version and review the changelog when upgrading.

The spec stays JSON/YAML serializable. Pass callable objects to `run_checks`,
not into the spec's string-reference fields. Supplying both a direct callable and
a reference for the same role raises `ValueError`. A pipeline factory cannot be
combined with either feature or forecast functions. Feature and forecast
functions may be used together, including a direct function for one boundary
and an import reference for the other.

The default gate validates structure and declared availability before invoking
your code. Runtime budgets apply to direct functions and factories too. Probe
inputs/outputs are copied as in CLI runs, but globals, files, models captured
outside the function, and mutable objects within dataframe cells are not process-isolated.
There is no hard wall-clock timeout.

Missing primary data, conflicting arguments, and primary file-loading problems
raise configuration/IO exceptions. Invalid contracts raise Pydantic validation
errors. Exceptions inside individual checks become typed ERROR results;
unusable or failing runtime callables can produce loud SKIPPED results.

Revision sidecars still use `RevisionSpec.data` paths. Fitted-model inspection
still uses `MLForecastAdapterSpec` import references or saved-model paths. YAML
loading requires `data`. The existing `plan_execution(spec)` API describes
file-backed, reference-configured runs; it does not plan directly supplied functions.

## Inspect and enforce results

```python
for result in report.results:
    print(result.check_id, result.status, result.detail or result.summary)
    for violation in result.violations:
        print(violation.code, violation.evidence)

print(report.model_dump_json(indent=2))
print(report.coverage, report.runtime_calls)

# In a job or command-line script:
raise SystemExit(report.exit_code(strict=True))
```

Use `exit_code(strict=True)` when every configured comparison must complete.
`report.failed` alone does not include skipped checks. Without a callable the
runtime check is SKIPPED, which strict mode blocks. The library returns a report
and never exits the process itself.

## Runnable examples

```bash
python examples/python_api/pandas_example.py
python examples/python_api/mlforecast_example.py  # requires the nixtla extra
```

The [pandas example](../examples/python_api/pandas_example.py) checks clean/leaky
features, report round-tripping, and SARIF. The
[MLForecast example](../examples/python_api/mlforecast_example.py) fits a real
model inside a direct forecast function across two origins with three modes,
then verifies an intentionally leaky forecast fails. Both use synthetic data in
memory and assert expected outcomes; they exit zero when those assertions pass.

For factory implementations, see the [replay contract](ADOPTION_GUIDE.md#4-fresh-pipeline-replay).
Pass your factory as `run_checks(spec, frame=frame, pipeline_factory=create_pipeline)`;
the returned object's `predict` receives the exact configured origin.
