# ForecastGuard

**Catch forecasting pipeline errors before you trust a backtest.**

[![CI](https://github.com/ankitlade12/ForecastGuard/actions/workflows/ci.yml/badge.svg)](https://github.com/ankitlade12/ForecastGuard/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-blue)](SUPPORT_MATRIX.md)
[![License](https://img.shields.io/badge/License-Apache--2.0-green)](LICENSE)

[Documentation](docs/README.md) · [Examples](examples/README.md) ·
[Support matrix](SUPPORT_MATRIX.md) · [Benchmarks](docs/BENCHMARK_FEASIBILITY.md) ·
[Contributing](CONTRIBUTING.md)

ForecastGuard is a Python library, CLI and GitHub Action for validating forecasting
backtests. It checks train/validation boundaries, covariate availability and whether
features or predictions change when unavailable future inputs are perturbed.
Use it with your existing forecasting code before comparing models or accepting
a pipeline change.

It runs locally with pandas dataframes, supports configurable column names, and
includes an optional MLForecast integration. No account or hosted service is required.

> **Status: pre-release.** The features below are implemented in this checkout.
> Install from source while release review is in progress; these instructions do
> not depend on a PyPI release. Runtime results cover the configured pipeline,
> origins and probes. A PASS does not prove the absence of every kind of leakage.

![A forecasting cutoff separating training data from future observations](docs/assets/forecastguard-demo.gif)

## Try a working example

With Python 3.12 or 3.13, clone the repository and install the library:

```bash
git clone https://github.com/ankitlade12/ForecastGuard.git
cd ForecastGuard
python -m pip install .
```

Then use the library directly:

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

Change `shift(1)` to `shift(-1)` to see `FG-LEAK-001` detect a future-target
dependency. DataFrames and local functions work directly, without YAML or
temporary files. See the [Python API](docs/PYTHON_API.md) for forecast functions,
pipeline factories, typed results, and a runnable MLForecast example.

## CLI quickstart

With Python 3.12 or 3.13 and [uv](https://docs.astral.sh/uv/getting-started/installation/)
installed, run from a checkout containing these features:

```bash
git clone https://github.com/ankitlade12/ForecastGuard.git
cd ForecastGuard
uv sync
uv run forecastguard run --spec examples/adoption/replay-clean.yaml --strict
```

The clean pipeline passes all three checks and exits `0`. Now run the paired
pipeline that uses future targets during preprocessing:

```bash
uv run forecastguard run --spec examples/adoption/replay-leaky.yaml --strict
```

This intentionally exits `1` with `FG-FORECAST-001`. Its diagnostics identify
future target sensitivity. Both examples use bundled data and require no model
downloads, API keys or optional MLForecast dependency.

Already have a checkout? Start at `uv sync`. To install into an existing Python
environment instead, use `python -m pip install -e .` from the repository root
and omit the `uv run` prefix.

## Connect your pipeline

For Python applications, pass your existing function directly:

```python
report = forecastguard.run_checks(spec, frame=frame, forecast_fn=your_forecast)
```

`your_forecast(train, future)` returns keyed horizon predictions. Install
`python -m pip install '.[nixtla]'` from the checkout for the optional MLForecast
dependency. The [in-memory example](examples/python_api/mlforecast_example.py)
shows fitting and prediction inside the tested function.

For MLForecast, generate a spec and a wrapper around your own unfitted model factory:

```bash
uv sync --extra nixtla
uv run --extra nixtla forecastguard init --data data.csv --framework mlforecast \
  --model-factory yourpackage.models:create_model
uv run --extra nixtla forecastguard plan --spec forecastguard.yaml
uv run --extra nixtla forecastguard run --spec forecastguard.yaml --strict --diagnose
```

Replace `yourpackage.models:create_model` with your importable factory returning
a fresh `MLForecast` instance. The prompts collect column mappings, horizon,
cutoff and explicit future/static covariate roles. Omitting `--model-factory`
creates a reference model for trying the workflow; its result only validates that
reference wrapper. See the [setup guide](docs/ADOPTION_GUIDE.md).

For other Python pipelines, use `--framework python` and connect one of these
interfaces in your YAML:

| Interface | Use it to validate |
|---|---|
| `feature_fn: 'module:build_features'` | Feature values before each cutoff |
| `forecast_fn: 'module:predict'` | Predictions from training and future frames |
| `pipeline_factory: 'module:create_pipeline'` | Preprocessing and fitting reconstructed inside each execution |

The [configuration reference](docs/CONFIGURATION.md) defines each contract.
Code executed outside the configured interface is outside the behavioural test.

## What you get

| Capability | What it answers |
|---|---|
| Cutoff integrity | Are identifiers, timestamps and single/rolling/CV horizons consistent? |
| Covariate availability | Are declared future/static inputs valid and available when needed? |
| Behavioural leakage probes | Do unavailable future inputs influence features or forecasts? |
| Guided setup | How do I connect my data and model without guessing column roles? |
| Execution planning and coverage | What will run, how many calls can it make, and what actually ran? |
| Targeted diagnostics | Which individual input interventions changed the output after a failure? |
| Fresh pipeline replay | Does rebuilding preprocessing and fitting reveal future dependence? |
| Historical revisions | Do supplied inputs match the latest version published by each origin? |
| CI reports | Can I gate a change and inspect JSON, SARIF or a GitHub summary? |

These capabilities share three registered checks and one typed report. See
[all five adoption workflows](docs/ADOPTION_GUIDE.md) for runnable examples and
[the support matrix](SUPPORT_MATRIX.md) for tested coverage and limitations.

## Read the result

| Check status | Meaning | Exit under `--strict` |
|---|---|---|
| `PASS` | The configured check completed without a detected violation | `0` if every check passes |
| `FAIL` | A contract violation or future-input dependency was detected | `1` |
| `SKIPPED` | A required input or executable comparison was unavailable | `1` |
| `ERROR` | A check raised unexpectedly | `1` |

Without `--strict`, skips are visible but do not alone make the exit code nonzero.
Use strict mode when a backtest must have runtime coverage. A materialized CV
output supports structural validation but cannot supply raw training history
for behavioural probes.

```bash
uv run forecastguard run --spec examples/adoption/replay-clean.yaml --strict \
  --json-output forecastguard-report.json --sarif-output forecastguard-report.sarif
```

See [CLI and report reference](docs/CLI.md), [troubleshooting](docs/TROUBLESHOOTING.md)
and [CI integration](docs/CI.md). Plans do not execute user code; runtime checks do.

## Evidence and limits

In the [recorded local feasibility benchmark](docs/BENCHMARK_FEASIBILITY.md), three
perturbation modes detected 72/72 observable seeded leaks and accepted 72/72 clean
controls. The same evaluation missed all 27 deliberately constructed boundary
leaks. These are curated cases, not an estimate of accuracy on arbitrary pipelines.

Runtime probing repeats your computation. The recorded backtest-plus-gate cost
was 4.78–7.41 times the baseline across measured workloads. Use `plan` and an
explicit call budget before applying it to expensive fitting jobs. Diagnostics
and the new replay/revision workflows are not covered by those earlier timings.

Frozen preprocessing, external state, incorrect availability declarations,
untested origins and changes below numeric tolerance can escape detection.
Revision histories enforce a declared snapshot policy; they are supplied evidence,
not independent provenance. See the [security and execution policy](SECURITY.md).

## Get help or contribute

Start with [support](SUPPORT.md) for setup questions and reproducible bug reports.
Small anonymized pipelines that expose a missed leak, a false alarm or an
unexpected skip are especially useful. Contributions to docs and examples are welcome.

- [Contributor setup and checks](CONTRIBUTING.md)
- [Roadmap](ROADMAP.md) and [changelog](CHANGELOG.md)
- [Architecture](docs/ARCHITECTURE.md) and [engineering decisions](docs/DECISIONS.md)
- [Code of conduct](CODE_OF_CONDUCT.md) and [security reporting](SECURITY.md)

Licensed under the [Apache License 2.0](LICENSE).
