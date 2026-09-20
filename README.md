# ForecastGuard

**Check your forecasting pipeline before you trust its backtest.**

[![CI](https://github.com/ankitlade12/ForecastGuard/actions/workflows/ci.yml/badge.svg)](https://github.com/ankitlade12/ForecastGuard/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-blue)](https://github.com/ankitlade12/ForecastGuard/blob/main/SUPPORT_MATRIX.md)
[![License](https://img.shields.io/badge/License-Apache--2.0-green)](https://github.com/ankitlade12/ForecastGuard/blob/main/LICENSE)

[Python API](https://github.com/ankitlade12/ForecastGuard/blob/main/docs/PYTHON_API.md) ·
[Documentation](https://github.com/ankitlade12/ForecastGuard/blob/main/docs/README.md) ·
[Examples](https://github.com/ankitlade12/ForecastGuard/tree/main/examples) ·
[Report a bug](https://github.com/ankitlade12/ForecastGuard/issues/new/choose)

A backtest can look better because a feature or prediction used information that
wasn't available at the forecast origin. ForecastGuard reruns your code with
unavailable future inputs changed and reports when the output moves.

Use it as a **Python library**, a **CLI**, or a **GitHub Action**. It works with
pandas DataFrames and your existing functions, including MLForecast pipelines.
Runs stay in your environment; no account or hosted service is needed.

> **Pre-release:** `0.1.0` is being prepared for PyPI. Use a source checkout
> containing the Python API ([PR #4](https://github.com/ankitlade12/ForecastGuard/pull/4)
> until merged). A successful check covers the configured probes; it does not
> certify that a pipeline is free of every kind of leakage.

## Install

From the repository checkout, with Python 3.12 or 3.13:

```bash
python -m pip install .
```

Optional integrations:

```bash
python -m pip install '.[nixtla]'   # MLForecast
python -m pip install '.[parquet]'  # Parquet datasets
```

The first PyPI upload is pending. Registry installation instructions will replace
these source-install commands after the release is verified.

## Try a working example

Pass a DataFrame and a function. No YAML, import strings, or temporary CSV files.

```python
import pandas as pd
from forecastguard import ForecastSpec, run_checks

frame = pd.DataFrame({
    "unique_id": ["A"] * 6,
    "ds": pd.date_range("2024-01-01", periods=6, freq="D"),
    "y": [1.0, 3.0, 2.0, 4.0, 6.0, 5.0],
})

def features(data):
    return data[["unique_id", "ds"]].assign(
        lag=data.groupby("unique_id")["y"].shift(1)
    )

spec = ForecastSpec(cutoff="2024-01-04", horizon=2, freq="D")
report = run_checks(spec, frame=frame, feature_fn=features)
assert report.exit_code(strict=True) == 0
```

Now change `shift(1)` to `shift(-1)`. The feature reads tomorrow's target, the
runtime check fails with **`FG-LEAK-001`**, and the strict exit code is `1`.
Inspect the result in Python:

```python
for result in report.results:
    print(result.check_id, result.status)
    for violation in result.violations:
        print(violation.code, violation.evidence)

print(report.model_dump_json(indent=2))
```

Column names, rolling origins, future covariates, perturbation modes and call
budgets are configurable. See the
[Python API guide](https://github.com/ankitlade12/ForecastGuard/blob/main/docs/PYTHON_API.md).

## Connect your forecast

Use the same function you use in your backtest:

```python
report = run_checks(spec, frame=frame, forecast_fn=predict)
```

`predict(train, future)` returns a DataFrame of identity/time keys and numeric
predictions for the complete horizon. Fit preprocessing and models inside that
function to include them in the test. For a fresh object on every execution, use
`pipeline_factory=create_pipeline`.

| Boundary | What is compared |
|---|---|
| `feature_fn(frame)` | Feature values before each forecast origin |
| `forecast_fn(train, future)` | Predictions over each forecast horizon |
| `pipeline_factory()` | Predictions after reconstructing preprocessing and fitting |

Run the complete examples from the checkout:

```bash
python examples/python_api/pandas_example.py
python examples/python_api/mlforecast_example.py  # requires the nixtla extra
```

Both verify a clean pipeline passes and an intentional leak fails.

## Three checks, one report

| Check | Detects |
|---|---|
| **Cutoff integrity** | Duplicate keys, invalid identifiers, and incomplete or misaligned forecast windows |
| **Known-future covariates** | Invalid declarations, incomplete coverage, late availability, and undeclared raw model inputs when adapter evidence is configured |
| **Runtime leakage** | Features or predictions that change when unavailable future inputs are perturbed |

Optional workflows add historical revision contracts, per-probe coverage,
execution budgets and targeted diagnostics. Read the
[adoption guide](https://github.com/ankitlade12/ForecastGuard/blob/main/docs/ADOPTION_GUIDE.md)
for their contracts and examples.

## CLI and CI

With the package installed, run from the checkout:

```bash
forecastguard run --spec examples/adoption/replay-clean.yaml --strict
forecastguard run --spec examples/adoption/replay-leaky.yaml --strict
```

The first exits `0`; the second intentionally exits `1`. For your own pipeline,
use `forecastguard init --data data.csv` to create a spec, then
`forecastguard plan --spec forecastguard.yaml` to inspect the planned work.

| Status | Meaning | Strict gate |
|---|---|---|
| `PASS` | No violation observed in the completed checks | Allows the run if every check passes |
| `FAIL` | A contract violation or future dependence was detected | Blocks |
| `SKIPPED` | A required comparison could not complete | Blocks |
| `ERROR` | An unexpected error prevented a check | Blocks |

Use `report.exit_code(strict=True)` in Python or `--strict` in CI. Without strict
mode, skips alone do not block. JSON, SARIF and GitHub summaries share the same
report. See the [CI guide](https://github.com/ankitlade12/ForecastGuard/blob/main/docs/CI.md)
for the composite Action and artifact setup.

## What a PASS does—and doesn't—mean

The probes cover only the configured data, origins, functions, modes and numeric
tolerance. Frozen preprocessing, external caches, inaccurate availability
claims, and untested origins can hide leaks. A materialized CV output can be
checked structurally but lacks the raw history needed for runtime probes.

The [dated feasibility study](https://github.com/ankitlade12/ForecastGuard/blob/main/docs/BENCHMARK_FEASIBILITY.md)
caught 72/72 observable seeded leaks with three modes and accepted 72/72 clean
controls. It missed all 27 constructed boundary leaks. These are curated cases,
not production recall estimates, and the measurements predate the newer APIs.

Probes repeat your model work. The study measured total backtest-plus-gate costs
of 4.78–7.41× baseline. Use explicit call budgets for expensive fitting; call
budgets are not timeouts. See the
[support matrix](https://github.com/ankitlade12/ForecastGuard/blob/main/SUPPORT_MATRIX.md)
and [execution policy](https://github.com/ankitlade12/ForecastGuard/blob/main/SECURITY.md).

## Help and contribute

[Support](https://github.com/ankitlade12/ForecastGuard/blob/main/SUPPORT.md) ·
[Contributing](https://github.com/ankitlade12/ForecastGuard/blob/main/CONTRIBUTING.md) ·
[Roadmap](https://github.com/ankitlade12/ForecastGuard/blob/main/ROADMAP.md) ·
[Changelog](https://github.com/ankitlade12/ForecastGuard/blob/main/CHANGELOG.md)

Small reproducible pipelines that reveal missed leaks, false alarms or unexpected
skips are especially useful. Licensed under Apache-2.0.
