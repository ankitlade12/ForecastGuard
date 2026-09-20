# Roadmap

ForecastGuard ships in thin, independently useful slices. Status reflects the
implementation in this checkout; publication remains pending.
[GitHub releases](https://github.com/ankitlade12/ForecastGuard/releases) are the publication record.

## Implemented

### v0.1 — Foundation ✅
Package skeleton, typed contract, `Check` protocol + stubs, runner, Click CLI,
docs, OSS hygiene, CI + publish workflows, composite GitHub Action.

### Slice 2 — Cutoff integrity (deterministic) ✅
Duplicate `(id, ds)`, missing training history, and empty/short/misaligned
holdout vs `horizon`/`freq` — deterministic validation, structured evidence per
violation (`FG-CUTOFF-*`). Shipped with a clean→broken example pair. See
DECISIONS D-011.

### Slice 3 — Known-future covariates (contract diff) ✅
Validates `spec.future_covariates` against the data: declared-but-missing column
(`FG-FUTURE-001`) and declared-but-empty-in-holdout (`FG-FUTURE-002`); undeclared
covariates surfaced as past-only. Clean→broken example pair. See DECISIONS D-012.

### Slice 4 — Runtime leakage (the moat) ✅
Behavioural perturbation: contract-aware future mask, determinism probe, re-run
`feature_fn`, diff pre-cutoff values (`FG-LEAK-001`). Forward-looking features
over *declared* future covariates are not flagged. Headline leaky→clean demo in
`examples/runtime_leakage/`. See DECISIONS D-013. **All three checks are now
implemented.**

### P0 — Trustworthy public alpha ✅
Bounded runtime PASS semantics, null-ID protection, strict future/static
availability contracts, versioned JSON output, and Apache-2.0 licensing. See
DECISIONS D-014.

### P1 — Rolling-origin Nixtla contract ✅
Multi-cutoff raw history, Nixtla `cutoff_col` output, per-window evidence, and
optional fitted-MLForecast consumed-feature inspection (`FG-FUTURE-004`).

### P2 — Forecast-level behavioural perturbation ✅
`forecast_fn(train_df, future_df)` detects unavailable exogenous input use and
teacher forcing (`FG-FORECAST-001`) across every origin.

### P3 — Evidence and scale ✅
Deterministic perturbation modes, point-in-time availability, explanation-only
AST hints, a 7-case mutation corpus, and a 365k-row scale benchmark. Pandas
measured ~171k rows/s after grouping optimization, so Polars is not justified.

### Slice 5 — Ship locally ✅
GitHub annotations/summary, JSON + SARIF artifacts, hardened composite Action,
Python 3.12/3.13 CI, Nixtla tutorial, README asset, and release workflow.

### Five adoption features ✅

Guided setup with an optional MLForecast wrapper; data-only execution plans and
per-probe coverage; budgeted single-input diagnostics; fresh pipeline-factory
replay; and publication-time revision validation. Existing callables and the
three-check registry remain supported. See [the adoption guide](docs/ADOPTION_GUIDE.md)
for runnable examples, contracts and coverage limits.

### Python library API ✅

Top-level `run_checks` accepts DataFrames, direct feature/forecast functions,
and fresh pipeline factories. YAML is optional for Python callers. Examples,
API documentation and installed-wheel CI coverage are included. See
[the Python guide](docs/PYTHON_API.md) and D-023.

## Release pending

- Review and merge the Python API change through the protected `main` branch.
- Verify PyPI trusted publishing and curate the first release notes using the
  [release runbook](docs/RELEASING.md).
- Publish the first version and test the registry-installed library and Action.
- Refresh the dated feasibility measurements against the release revision;
  pilot with independent forecasting pipelines before expanding scope.

## Later
- Hosted CI tier — checks on every PR, dashboards.
- Additional forecasting-framework adapters beyond MLForecast.
- Polars support after profiling demonstrates the need.

This roadmap mirrors `docs/ForecastGuard_PRD.md` §9 and the slice plans in
the [historical plan index](docs/plans/README.md). Dated plans record what was
true at implementation time; they are not the current backlog.
