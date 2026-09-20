# ForecastGuard — Architecture Map

One-page entry point for anyone (human or AI) working in this repo.

## Where to look for what

| If you need to understand... | Read... |
|---|---|
| **Product intent, the 3 checks, scope, GTM** | [`ForecastGuard_PRD.md`](./ForecastGuard_PRD.md) — the canonical product spec |
| **Engineering decisions, rationale, tradeoffs** | [`DECISIONS.md`](./DECISIONS.md) — living decision log, dated entries |
| **What's planned / in flight** | [Roadmap](../ROADMAP.md); [dated plan archive](plans/README.md) |
| **The input contract** | [`forecastguard/models/spec.py`](../forecastguard/models/spec.py) |
| **The output contract** | [`forecastguard/models/report.py`](../forecastguard/models/report.py) |
| **How to set up and use the library** | [User documentation](README.md) |
| **How to test and contribute** | [Contributing](../CONTRIBUTING.md) + `Makefile` |

The PRD describes the product as intended. DECISIONS.md captures engineering
judgment that fills gaps or evolves beyond the PRD.

## Data flow

The public `forecastguard.run_checks(spec, frame=..., feature_fn=...,
forecast_fn=..., pipeline_factory=...)` API accepts in-memory data and direct
callables. The serializable spec describes the validation contract; direct
callables live in `CheckContext`. File-based CLI runs enter the same runner.
See [Python API](PYTHON_API.md) for precedence and conflict rules.

`init` scaffolds validated configuration and optional MLForecast callables.
`planning.plan_execution` uses `runner.data_context` to load data and revision
sidecars without importing executable configuration. `run` keeps the same three
checks; revision evidence is composed into known-future validation. Optional
`replay.replay_forecast` reconstructs a pipeline instance for every raw-history
forecast probe. `execution` tracks requested comparisons and actual calls.
After an established behavioural failure, `diagnostics` runs budgeted single-input
interventions that cannot change the original verdict. Report coverage and
diagnostic fields are additive to schema 1.0 and retained by all renderers.

See [the adoption guide](ADOPTION_GUIDE.md) for contracts and complete examples.

The default runner validates structure and declared covariates before importing
or invoking user code. Failed prerequisites produce a runtime SKIP; prerequisite
FAIL/ERROR results always block, while SKIPPED results block in strict mode. Only
valid inputs reach optional model inspection, then budgeted runtime execution.
Explicit custom check sequences retain the caller's order and prerequisites.

Behavioural probes share output indexing, numeric tolerances, evidence sampling,
and result aggregation in `checks/comparison.py`. `CheckContext.windows` lazily
prepares timestamps and origin grids once for feature and forecast probes; masks
are generated per origin to avoid retaining a full dataframe per window.

### Verdict contract

| Status | Meaning | Gate |
|---|---|---|
| PASS | Requested comparisons completed; no violation observed under the declared inputs, windows, modes and tolerance | Exit 0 |
| FAIL | At least one violation was established; `detail` also preserves incomplete probes | Exit 1 |
| SKIPPED | Missing prerequisites, invalid callable output, nondeterminism, unsupported probes, or exceeded call budget prevented a complete verdict | Exit 1 with `--strict`, otherwise 0 |
| ERROR | An unexpected execution failure prevented evaluation | Exit 1 |

Runtime feature outputs may omit warm-up rows but need nonempty, unique,
consistent keys. Forecast outputs must cover every series and horizon timestamp
exactly once, with finite numeric baseline predictions. Inputs and output
snapshots are isolated between executions. Callables must not depend on mutable
external state: dataframe copies do not isolate globals, files, or model caches.

A later skipped probe cannot erase a previous violation. Every configured mode
continues when another mode is unsupported. JSON, human output, GitHub summaries
and SARIF retain incomplete details alongside failures. Source hints remain
possible explanations in evidence, not asserted violation locations.

CV-output validation checks existing `(series, cutoff)` pairs, allowing different
origins per series. It cannot discover an entirely omitted series/window without
an external roster of expected pairs.

```
forecastguard.yaml or Python ForecastSpec + DataFrame/callables
      │  config.load_spec()
      ▼
  ForecastSpec ───────────────► runner.run_checks()
                                      │  data_context: load frame and histories
                                      │  validate prerequisites before user imports
                                      ▼
                                 CheckContext
                                      │  ordered checks; lazy runtime setup
            ┌──────────────┬──────────┴───────────┐
            ▼              ▼                        ▼
   CutoffIntegrity   KnownFuture            RuntimeLeakage
     Check             CovariatesCheck        Check (the moat)
            └──────────────┴──────────┬───────────┘
                                      ▼
                                   Report ──► human / JSON / SARIF / GitHub + exit code
```

## Module layout

```
forecastguard/
├── models/
│   ├── spec.py          # ForecastSpec — the declared input contract
│   ├── report.py        # Report, CheckResult, Violation, Severity, CheckStatus
│   ├── adapter.py       # fitted-framework consumed-feature evidence
│   ├── execution.py     # typed coverage and diagnostic evidence
│   └── hint.py          # explanation-only source locations
├── checks/
│   ├── protocol.py      # Check protocol + CheckContext (the run bundle)
│   ├── cutoff.py        # Check 1 — deterministic dataframe validation
│   ├── known_future.py  # Check 2 — declared availability contract
│   ├── revisions.py     # revision evidence composed into Check 2
│   ├── runtime_leak.py  # Check 3 — feature perturbation + aggregation
│   └── forecast_leak.py # forecast-output perturbation component
├── adapters/
│   ├── mlforecast.py    # optional ts.features_order_ introspection
│   └── mlforecast_runtime.py # generated-wrapper fit/predict integration
├── setup.py             # validated init and optional wrapper generation
├── planning.py          # data-only readiness and execution counts
├── execution.py         # actual runtime accounting and probe coverage
├── replay.py            # fresh pipeline factory adaptation
├── diagnostics.py       # budgeted explanations after behavioural failures
├── windows.py           # shared single/rolling/CV window semantics
├── perturb.py           # nullify/noise/sign_flip contract-aware inputs
├── explain.py           # AST hints after behavioural proof only
├── render.py            # SARIF + GitHub renderers over typed Report
├── runner.py            # build_context + run_checks (orchestration + IO)
├── config.py            # load_spec (YAML -> validated ForecastSpec)
└── cli.py               # Click entry points: init, plan, run

tests/                   # pytest tiers: unit, contract, integration
examples/                # leaky -> clean demo specs and data
action.yml               # composite GitHub Action wrapping the CLI
docs/                    # PRD, ARCHITECTURE, DECISIONS, plans
```

## Non-negotiable architectural principles

1. **Nixtla-native contract (D-001).** The data shape is `unique_id` / `ds` /
   `y` by default. Column names are configurable on the spec, never hardcoded in
   a check.
2. **Behavioural verdicts, source explanation (D-003/D-018).** Leakage verdicts
   come only from perturb-and-diff. AST inspection can annotate a proven failure
   with a likely source line; it never creates or suppresses a verdict.
3. **Check protocol + stub pattern (D-004).** Every check implements `Check` and
   depends only on `CheckContext` — never on file IO. A check ships as a stub
   first (loud SKIP) so the runner and CLI are buildable and testable before the
   logic lands. Same discipline GoldMind applies to connectors and parsers.
4. **Structured outputs everywhere (D-005).** Checks return typed `CheckResult`
   objects, never free text. The CLI renders them; the hosted tier will too.
5. **Skip loudly, never pass silently (D-006).** A missing precondition (e.g. no
   `feature_fn`) yields a prominent `SKIPPED`, not a green check.
6. **The exit code is the gate (D-007).** `fail`/`error` → exit 1. `--strict`
   promotes loud skips to failures. Without strict mode, PASS/SKIPPED runs can exit 0.
7. **Honest scope.** Detects common, high-impact errors — not "all leakage."

## Testing philosophy

- **unit** — models (serialization round-trips, exit-code logic), each check's
  rule boundaries, config loading.
- **contract** — every check satisfies the `Check` protocol; the registry stays
  consistent. (The protocol analogue of GoldMind's connector parity tests.)
- **integration** — `runner.run_checks` + the CLI run end to end against a fixed
  example and produce the expected report and exit code; the optional Nixtla
  extra runs a real fitted-MLForecast adapter test.
- **public benchmarks** — mutation controls establish detector recall on seeded
  cases; a JSON scale probe records whether a new backend is justified.

Quality gates are commit-time (pre-commit: ruff + mypy + unit tier) plus the CI
workflow (`.github/workflows/ci.yml`) on push/PR.
