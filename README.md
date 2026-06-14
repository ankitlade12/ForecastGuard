# ForecastGuard CI 🛡️📈

**The quality gate for forecasting backtests — before a model-selection agent trusts them.**

[![PyPI](https://img.shields.io/badge/pypi-forecastguard-blue.svg)](https://pypi.org/project/forecastguard/)
[![Python versions](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://pypi.org/project/forecastguard/)
[![CI](https://img.shields.io/badge/CI-github_actions-blue.svg)](.github/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-TBD-lightgrey.svg)](#license)

**An open-source CLI and GitHub Action that validates your forecasting pipeline before its backtest is trusted. Three deliberately narrow checks — cutoff integrity, known-future covariates, and runtime leakage — catch the pipeline errors that silently inflate a backtest and trick automated model selection into shipping the wrong model. Nixtla-native (`unique_id` / `ds` / `y`), no hosted service.**

Links: [Product spec](docs/ForecastGuard_PRD.md) | [Architecture](docs/ARCHITECTURE.md) | [Decisions](docs/DECISIONS.md) | [Roadmap](ROADMAP.md)

> **Status (v0.1).** All three checks are implemented and run end to end — **cutoff integrity** and **known-future covariates** (deterministic), and **runtime leakage** (behavioural perturbation, the moat). See [`examples/`](examples/) for clean→broken and leaky→clean pairs. Next is packaging and a first PyPI release (Slice 5, see the [Roadmap](ROADMAP.md)). Honest scope is a feature: ForecastGuard detects **common, high-impact** pipeline errors, not "all leakage."

## The problem

A model-selection agent watches SMAPE drop from 44 to 19, ranks that model #1, and ships it. But the score was inflated by **future leakage** in the feature pipeline. Automated, backtest-driven selection doesn't just *tolerate* leakage — it **systematically prefers** the leaky model, because leakage is what makes the backtest look best. The agent has no nose for "this 19 is a lie." ForecastGuard is that nose.

## The three checks

| Check | Catches | How |
|---|---|---|
| **Cutoff integrity** | Validation rows on/before the cutoff; bad horizons; duplicate timestamps | Deterministic dataframe check — zero false positives |
| **Known-future covariates** | Variables used at predict time that won't exist in production | Declared-vs-used contract diff |
| **Runtime leakage** *(the moat)* | Feature engineering that reads across the cutoff (centered windows, full-frame scalers) | Behavioural perturbation — not source parsing |

### Why the leakage check is the moat

**A leak-free feature at time `t` cannot change when the future is hidden.** ForecastGuard re-runs your feature function on future-masked data and diffs the pre-cutoff values. It proves leakage *behaviourally* — catching what code-parsing misses, and never false-positiving on a correctly-built trailing feature. When you give it only a finished frame (no callable feature function), it **skips loudly** rather than passing silently.

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
      - uses: ankitlade12/ForecastGuard@v0   # composite action; wraps the CLI
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
forecastguard/   # the package: models, checks (protocol + 3 stubs), runner, config, cli
tests/           # pytest tiers: unit, contract, integration
examples/        # quickstart spec + data (leaky→clean demo lands in Slice 4)
docs/            # PRD, ARCHITECTURE, DECISIONS, plans
action.yml       # composite GitHub Action wrapping the CLI
```

## Scope & limitations

- Detects **common, high-impact** pipeline errors before backtests are trusted —
  **not** "all leakage."
- The runtime-leakage check needs a **callable feature function**; given only a
  finished frame it **skips loudly**, never silently.
- Not a drift monitor, not a forecasting library, not a SaaS — a local trust gate.

## Roadmap

See [ROADMAP.md](ROADMAP.md). All three checks are live; next up is Slice 5 —
ship: GitHub Action hardening, a Nixtla `cross_validation` tutorial, and a first
PyPI release.

## License

**TBD.** A license has not been chosen yet for this repository.

## Contributing

Issues and PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
