# ForecastGuard

**Check your forecasting pipeline before you trust its backtest.**

ForecastGuard is a Python library, CLI and GitHub Action that checks forecasting
cutoffs, known-future covariate contracts, and runtime leakage. Pass a pandas
DataFrame and your existing functions, then inspect a typed report or use its
exit code to gate model selection.

```bash
python -m pip install forecastguard
```

Start with the [Python quickstart](PYTHON_API.md#quickstart), run the
[clean and leaky examples](examples.md), or integrate the [CLI](CLI.md)
into your existing workflow. Python 3.12 and 3.13 are covered by CI.

These docs follow `main`. For released behavior, see the
[0.1.0 release](https://github.com/ankitlade12/ForecastGuard/releases/tag/v0.1.0).
Checks cover the configured probes; a passing result does not prove the absence
of every kind of leakage. See [scope and limitations](ForecastGuard_PRD.md#6-honest-scope).

```{toctree}
:caption: Get started
:maxdepth: 1

PYTHON_API
examples
tutorials/nixtla-rolling
```

```{toctree}
:caption: Reference and integration
:maxdepth: 1

api
CONFIGURATION
CLI
ADOPTION_GUIDE
CI
TROUBLESHOOTING
```

```{toctree}
:caption: Evidence and development
:maxdepth: 1

BENCHMARK_FEASIBILITY
ARCHITECTURE
DECISIONS
ForecastGuard_PRD
COMPETITIVE_LANDSCAPE
RELEASING
README
```
