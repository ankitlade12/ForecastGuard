# Changelog

All notable changes to ForecastGuard are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to
follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Python library API
- Public `forecastguard.run_checks` accepts an in-memory DataFrame and direct
  feature/forecast callables or a fresh pipeline factory; `ReplayPipeline` is
  exported for typed integrations.
- `ForecastSpec.data` is optional for Python runs with `frame`; YAML continues
  to require a data path. Conflicting callable sources are rejected explicitly.
- Direct inputs share the CLI's prerequisite validation, runtime call budgets,
  diagnostics, coverage and typed reports. No temporary dataset files are needed.
- Python-first quickstart, pandas/MLForecast examples and installed-wheel CI smoke.

### Documentation and onboarding
- Source-first quickstart with runnable clean/leaky examples and explicit exit codes.
- User documentation index, configuration/CLI references, CI guide, troubleshooting,
  support matrix and examples catalog.
- Updated contribution, security and issue-reporting instructions and release runbook.
- Optional-dependency CI now exercises generated MLForecast onboarding as well as
  the existing real-model integration.

### Adoption and replay
- Guided `init` creates a validated YAML spec and optional runnable MLForecast
  wrapper with explicit covariate declarations and custom column mappings.
- `plan` validates data without importing user code and reports primary calls,
  diagnostic limits, origins, and unmet requirements.
- Reports add per-origin/component/mode coverage, actual call counts, scope notes,
  targeted diagnostics and CLI rerun commands. `run --origin` narrows a rerun to
  configured raw-history origins.
- Optional `--diagnose` performs bounded single-input probes after a proven leak;
  diagnostic failures cannot replace the primary verdict.
- `pipeline_factory` reconstructs preprocessing/model instances for every probe.
  External state remains outside automatic isolation.
- Revision sidecars enforce a declared latest-available snapshot per origin;
  `FG-REV-001/002/003` report malformed history, unavailable values and mismatches.
- Reproducible local feasibility corpus and model-cost measurements are documented
  in `docs/BENCHMARK_FEASIBILITY.md`.

### Fixed
- Replay receives the explicit configured origin, including business-day origins
  that share a horizon. Diagnostics use the same origin.
- Revision validation compares exact stored values rather than applying runtime
  prediction tolerances; large numeric revisions can no longer pass unnoticed.
- Categorical comparisons use values rather than requiring identical category dictionaries.
- Coverage accounting indexes each component/origin instead of rescanning all
  probes. Revision histories are sorted once, and explicit init frequencies skip inference.
- Runtime probes isolate in-place functions and snapshot reused output buffers.
  Empty, partial, missing, or non-finite baseline forecasts cannot pass.
- A later unsupported perturbation no longer erases established leakage; partial
  failures remain visible in every report format.
- CV series may use different origins, and covariates may share an availability
  timestamp. Integer-valued inputs support numeric noise perturbations.
- Mutation benchmark controls require PASS rather than accepting any non-FAIL.
- `--format json --github` keeps annotations off JSON stdout.
- Null series identifiers now fail cutoff integrity with `FG-CUTOFF-014`
  instead of being dropped by dataframe grouping and producing a zero-series
  PASS.
- Declared future covariates now require complete coverage across available
  holdout rows (`FG-FUTURE-003`), and static declarations must exist and remain
  invariant within each series (`FG-STATIC-001/002`).
- `CutoffIntegrityCheck` now treats a missing declared `target_col` as a
  structural dataset error (`FG-CUTOFF-010`) instead of allowing a run to exit
  successfully against an incomplete ForecastGuard contract.
- `RuntimeLeakageCheck` now skips loudly when the feature function produces no
  comparable pre-cutoff rows, or when pre-cutoff rows do not align across the
  full/repeat/masked runs, instead of passing after a zero-row perturbation diff.

### Changed
- Default execution validates inputs before loading user code, with shared
  comparison and window preparation. `max_probe_calls` caps planned runtime
  executions; oversized plans skip before running probes.
- Source hints remain possible explanations in evidence rather than asserted
  source locations. A real MLForecast runtime example measures integration cost.
- Runtime PASS summaries now report bounded evidence (no sensitivity detected
  for the tested cutoff, mask, data, and tolerance) instead of claiming a
  universal proof that features are leak-free.
- `ForecastSpec` rejects duplicate or overlapping column-role declarations.
- The project is now licensed under Apache-2.0.
- The composite GitHub Action now installs ForecastGuard from the action checkout
  by default, with the `version` input reserved for explicitly testing a
  published PyPI version.

### Added
- Rolling-origin raw history (`cutoffs`) and Nixtla CV-output (`cutoff_col`)
  contracts with structured per-window evidence.
- Optional MLForecast adapter inspection of `ts.features_order_`; consumed raw
  exogenous inputs must be declared future/static (`FG-FUTURE-004`).
- Forecast-level behavioural perturbation through
  `forecast_fn(train_df, future_df)`, detecting unavailable exogenous inputs and
  teacher forcing as `FG-FORECAST-001`.
- Deterministic `nullify`, `noise`, and `sign_flip` perturbations with a seed.
- Point-in-time availability timestamps (`FG-AVAIL-001/002`) at historical
  event time and every forecast origin.
- Explanation-only AST source hints, SARIF 2.1.0, GitHub annotations and step
  summaries, plus JSON/SARIF Action artifacts.
- Public 7-case mutation corpus (7/7) and scale benchmark. The optimized pandas
  cutoff path processed 365,000 rows at ~171k rows/s on the reference machine;
  Polars is therefore deferred.
- Runnable rolling/Nixtla tutorial and real optional MLForecast integration.
- Versioned report serialization (`schema_version: "1.0"`) and
  `forecastguard run --format json` for machine-readable CI output.
- Integration coverage now exercises the advertised broken/clean examples for
  cutoff integrity, known-future covariates, and runtime leakage.
- **Slice 4 — Runtime-leakage check (the moat).** `RuntimeLeakageCheck` is now
  implemented (behavioural perturbation): contract-aware future masking, a
  determinism probe, and a pre-cutoff diff that flags any feature that reads
  across the cutoff (`FG-LEAK-001`). Forward-looking features over *declared*
  future covariates are not flagged. Ships with the headline
  `examples/runtime_leakage` (leaky→clean) demo and 10 unit tests. Semantics:
  DECISIONS D-013. **All three checks are now implemented.**
- **Slice 3 — Known-future-covariates check.** `KnownFutureCovariatesCheck` is
  now implemented (declared availability contract): `FG-FUTURE-001`
  (declared covariate not a column) and `FG-FUTURE-002` (declared covariate empty
  across the holdout); undeclared covariates surfaced as past-only. Ships with
  `examples/known_future` (clean→broken) and 8 unit tests. Semantics: DECISIONS
  D-012.
- **Slice 2 — Cutoff-integrity check.** `CutoffIntegrityCheck` is now
  implemented (deterministic, zero-false-positive): duplicate `(id, ds)`,
  missing training history, empty/short/misaligned holdout vs `horizon`/`freq`,
  with structured `FG-CUTOFF-*` evidence. Ships with `examples/cutoff_integrity`
  (clean→broken) and 15 unit tests. Semantics: DECISIONS D-011.
- **Slice 1 — Foundation.** Package skeleton, typed contract (`ForecastSpec`,
  `Report`, `CheckResult`, `Violation`), `Check` protocol + `CheckContext`, the
  runner, the Click CLI (`forecastguard run`), and a runnable `examples/quickstart`.
- Docs (PRD, ARCHITECTURE, DECISIONS D-001…D-013), agent instructions, OSS
  hygiene files, CI + PyPI publish workflows, and the composite GitHub Action.

### Release status
- All local P0–P3 and Slice 5 gates are complete. The first GitHub/PyPI release
  awaits valid maintainer authentication and trusted-publisher setup.

[Unreleased]: https://github.com/ankitlade12/ForecastGuard/commits/main
