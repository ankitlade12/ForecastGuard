# Five adoption features

> Historical implementation record. Status and verification below are as of this
> plan's date; see the [current roadmap](../../ROADMAP.md) and [plan index](README.md).

Implement guided init, static execution planning plus coverage, targeted diagnostics,
fresh pipeline replay, and revision-aware validation. Preserve the three registered
checks and existing callables. Additive report fields retain schema 1.0.

## Contracts

- `init`: interactive suggestions or explicit unattended arguments; never infer
  availability; never overwrite existing files. Generate YAML and an optional
  runnable MLForecast adapter, supporting a user's unfitted model factory.
- `plan`: read data and revision files, validate structural contracts, list origins,
  primary calls, optional diagnostic cap, budget and prerequisites. Never import
  adapters, factories or user callables. A blocked plan exits 1.
- Coverage: every configured origin/component/mode records completed PASS/FAIL,
  SKIP or not-run status. Count actual pipeline executions. No assurance for
  unconfigured origins, external state, or omitted pipeline stages.
- Diagnostics: optional one-column interventions AFTER an established behavioural
  failure. Recheck baseline determinism; report sensitivity/unchanged/incomplete
  and remediation guidance without changing the original verdict. Separate cap
  obeys remaining total call budget; rerun by explicit configured origin.
- Replay: `pipeline_factory()` creates a fresh object exposing
  `predict(frame, cutoff, spec)`. Every probe reconstructs the object and passes
  raw train+horizon input, so preprocessing/fitting inside predict is replayed.
  Mutually exclusive with legacy feature_fn/forecast_fn. This is in-process,
  not a sandbox; external state remains the user's responsibility.
- Revisions: sidecar long history per declared column with configurable value and
  availability columns, id/time keys from spec. For each origin, compare training
  inputs (and declared future horizon inputs) against the latest version published
  by that origin. Never compare future scoring targets. Ambiguous/missing history
  fails or skips loudly; never silently replace data. CV-only target history has
  no audit coverage. Compose results inside known-future covariates.

## Sequence / verification

Write behavioural tests first. Implement typed contracts and revision validation;
planning/coverage and replay; init and MLForecast wrapper; diagnostic probes and
renderers; examples/docs. Exercise custom columns, multi-origin versions,
missing/ambiguous revisions, absent imports, budgets, nondeterminism, frozen
preprocessing and input mutation. Run full pytest, ruff, strict mypy, real optional
MLForecast integration and CLI smoke flows. Do not publish or change detector
verdicts based on source hints or diagnostics.

## Completed verification

All five features are implemented with runnable examples in `examples/adoption/`
and usage contracts in `docs/ADOPTION_GUIDE.md`. Ruff lint/format and strict mypy
pass; the full suite passes 175 tests, including real MLForecast integration.
The optional dependency emits 22 pandas deprecation warnings.

CLI smoke runs verified planning and clean replay (exit 0), leaky replay and
targeted weather diagnostics (exit 1), and revision validation passing for an
early origin while failing the later stale snapshot. Regression coverage also
preserves a loaded revision violation when another sidecar is missing.
Implementation is local; no release or publication was performed.
