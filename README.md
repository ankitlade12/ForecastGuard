# ForecastGuard CI 🛡️📈

**The quality gate for forecasting backtests — before a model-selection agent trusts them.**

[![PyPI](https://img.shields.io/badge/pypi-forecastguard-blue.svg)](https://pypi.org/project/forecastguard/)
[![Python versions](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://pypi.org/project/forecastguard/)
[![CI](https://img.shields.io/badge/CI-github_actions-blue.svg)](.github/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

**An open-source CLI and GitHub Action that validates your forecasting pipeline before its backtest is trusted. Three deliberately narrow checks — cutoff integrity, known-future covariates, and runtime leakage — catch the pipeline errors that silently inflate a backtest and trick automated model selection into shipping the wrong model. Nixtla-native (`unique_id` / `ds` / `y`), no hosted service.**

Links: [Product spec](docs/ForecastGuard_PRD.md) | [Architecture](docs/ARCHITECTURE.md) | [Decisions](docs/DECISIONS.md) | [Competitive landscape](docs/COMPETITIVE_LANDSCAPE.md) | [Roadmap](ROADMAP.md)

![ForecastGuard blocks future data from crossing the forecast cutoff](docs/assets/forecastguard-demo.gif)

> **Status (v0.1 release candidate).** P0–P3 and Slice 5 are implemented locally:
> rolling-origin/Nixtla CV validation, fitted MLForecast feature inspection,
> feature- and forecast-level perturbation, point-in-time availability, source
> hints, JSON/SARIF/GitHub output, public benchmarks, and a hardened Action.
> External GitHub/PyPI publication still requires valid maintainer credentials.
> ForecastGuard detects **common, high-impact** errors, not "all leakage."

## The problem

A model-selection agent watches SMAPE drop from 44 to 19, ranks that model #1, and ships it. But the score was inflated by **future leakage** in the feature pipeline. Automated, backtest-driven selection doesn't just *tolerate* leakage — it **systematically prefers** the leaky model, because leakage is what makes the backtest look best. The agent has no nose for "this 19 is a lie." ForecastGuard is that nose.

## The three checks

| Check | Catches | How |
|---|---|---|
| **Cutoff integrity** | Bad single/rolling horizons; duplicate `(id, cutoff, ds)` keys; null IDs | Exact per-window grid validation |
| **Known-future covariates** | Invalid declarations, incomplete coverage, late availability, undeclared MLForecast inputs | Declared + fitted-model contract validation |
| **Runtime leakage** *(the moat)* | Centered/full-series features, actual-future exogenous use, teacher forcing | Feature and prediction perturbation — not source parsing |

### Why the leakage check is the moat

**A causal feature or forecast cannot change when unavailable future inputs are
hidden or perturbed.** ForecastGuard tests `nullify`, deterministic `noise`, and
`sign_flip` modes across every origin. An observed change establishes future
dependence behaviourally. AST hints may explain an already-proven failure, but
never create a verdict. No observed change is bounded evidence for the tested
windows, data, modes, and tolerance—not a universal proof.

Try it: [`examples/runtime_leakage`](examples/runtime_leakage/) ships a `clean.yaml`
and a `leaky.yaml` over the same data. The leaky one fails with two
`FG-LEAK-001`s (a centered window and a whole-series mean) while the honest
trailing `lag_1` stays clean:

```
[FAIL] Runtime leakage
   * critical: feature 'centered_mean_3' changes before the cutoff when the future is hidden … [FG-LEAK-001]
   * critical: feature 'y_vs_series_mean' changes before the cutoff when the future is hidden … [FG-LEAK-001]
```

## Quickstart

```bash
pip install forecastguard          # once published; for now: uv sync --extra dev
```

Describe your backtest in a `forecastguard.yaml`:

```yaml
name: demand-forecast-q3
data: data.csv            # long Nixtla frame: unique_id, ds, y, [covariates...]
id_col: unique_id
time_col: ds
target_col: y
cutoff: "2024-06-30"      # train rows have ds <= cutoff; validation after it
horizon: 28
freq: D
future_covariates: [holiday, promo_planned]
feature_fn: "myproject.features:build_features"   # optional; enables the leakage check
forecast_fn: "myproject.forecast:predict"         # optional; (train, future) -> predictions
perturbations: [nullify, noise, sign_flip]
# For rolling raw history, replace cutoff with:
# cutoffs: ["2024-05-31", "2024-06-30"]
# For MLForecast CV output, use: cutoff_col: cutoff
```

Run the gate:

```bash
forecastguard run --spec forecastguard.yaml
```

```
  ForecastGuard CI
  spec: demand-forecast-q3

  [PASS] Cutoff integrity
  [PASS] Known-future covariates
  [SKIP] Runtime leakage
         - no feature_fn declared in spec — nothing to perturb

  PASS - exit 0
```

For CI systems and other programmatic consumers, emit the versioned typed
report as JSON (stdout contains JSON only; the process exit code remains the
gate):

```bash
forecastguard run --spec forecastguard.yaml --format json
forecastguard run --spec forecastguard.yaml \
  --json-output report.json --sarif-output report.sarif --github
```

When the data is malformed, the cutoff check fails the run (exit 1) with
structured, per-series violations — see the
[clean→broken example](examples/cutoff_integrity/):

```
  [FAIL] Cutoff integrity
         * critical: 1 duplicate (id, ds) timestamp(s) … [FG-CUTOFF-001]
         * high: series 'B' holdout does not match 2 step(s) after the cutoff (too_few) (B) [FG-CUTOFF-004]
         * high: series 'C' has no holdout rows after the cutoff … (C) [FG-CUTOFF-003]
  FAIL - exit 1
```

`--strict` promotes loud skips to failures (exit 1) — use it once the checks are
live to demand that the runtime check actually ran.

## GitHub Action

Drop it into a workflow to gate every PR:

```yaml
# .github/workflows/forecast-guard.yml
name: ForecastGuard
on: [pull_request]
jobs:
  guard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ankitlade12/ForecastGuard@v0   # after the first GitHub release
        with:
          spec: forecastguard.yaml
          strict: "true"
```

## How it fits together

```
forecastguard.yaml ─► load_spec ─► ForecastSpec ─► build_context ─► run_checks ─► Report ─► exit code
                                                          │
                              ┌───────────────────────────┼───────────────────────────┐
                              ▼                            ▼                            ▼
                       Cutoff integrity          Known-future covariates        Runtime leakage
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full module map.

## Development

Python 3.12, uv-managed. Pydantic v2 contracts, ruff + mypy strict + pytest.

```bash
make setup     # uv sync --extra dev
make test      # pytest (unit / contract / integration tiers)
make lint      # ruff check + ruff format --check + mypy strict
make format    # auto-fix + format
make cli-demo  # run the CLI against examples/quickstart
```

**Adding a check:** new module in `forecastguard/checks/`, register it in
`checks.default_checks`, read column names from `ctx.spec` (never hardcode),
return a typed `CheckResult`. See [CONTRIBUTING.md](CONTRIBUTING.md) and
[.claude/claude.md](.claude/claude.md).

## Project layout

```
forecastguard/   # the package: models, checks (3 implemented checks), runner, config, cli
tests/           # pytest tiers: unit, contract, integration
examples/        # quickstart plus clean/broken demos for the shipped checks
docs/            # PRD, ARCHITECTURE, DECISIONS, plans
action.yml       # composite GitHub Action wrapping the CLI
```

## Scope & limitations

- Detects **common, high-impact** pipeline errors before backtests are trusted —
  **not** "all leakage."
- Runtime leakage needs a callable `feature_fn` and/or `forecast_fn`; a finished
  frame alone **skips loudly**, never silently.
- `cutoff_col` CV output validates structure and availability, but cannot run
  behavioural perturbation without raw training history.
- Not a drift monitor, not a forecasting library, not a SaaS — a local trust gate.

## Roadmap

See [ROADMAP.md](ROADMAP.md). All planned local phases are complete. The only
remaining release step is publishing the verified artifacts to GitHub/PyPI with
maintainer credentials.

## License

Licensed under the [Apache License 2.0](LICENSE).

## Contributing

Issues and PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
