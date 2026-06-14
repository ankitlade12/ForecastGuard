# ForecastGuard — Architecture Map

One-page entry point for anyone (human or AI) working in this repo.

## Where to look for what

| If you need to understand... | Read... |
|---|---|
| **Product intent, the 3 checks, scope, GTM** | [`ForecastGuard_PRD.md`](./ForecastGuard_PRD.md) — the canonical product spec |
| **Engineering decisions, rationale, tradeoffs** | [`DECISIONS.md`](./DECISIONS.md) — living decision log, dated entries |
| **What's planned / in flight** | [`plans/`](./plans/) — dated slice plans |
| **The input contract** | [`forecastguard/models/spec.py`](../forecastguard/models/spec.py) |
| **The output contract** | [`forecastguard/models/report.py`](../forecastguard/models/report.py) |
| **How to set up, run, test, contribute** | `Makefile` + `pyproject.toml` + `.pre-commit-config.yaml` |

The PRD describes the product as intended. DECISIONS.md captures engineering
judgment that fills gaps or evolves beyond the PRD.

## Data flow

```
forecastguard.yaml
      │  config.load_spec()
      ▼
  ForecastSpec ───────────────► runner.build_context()
                                      │  (load frame, import feature_fn)
                                      ▼
                                 CheckContext
                                      │  runner.run_checks()
            ┌──────────────┬──────────┴───────────┐
            ▼              ▼                        ▼
   CutoffIntegrity   KnownFuture            RuntimeLeakage
     Check             CovariatesCheck        Check (the moat)
            └──────────────┴──────────┬───────────┘
                                      ▼
                                   Report ──► cli._render() + exit code
```

## Module layout

```
forecastguard/
├── models/
│   ├── spec.py          # ForecastSpec — the declared input contract
│   └── report.py        # Report, CheckResult, Violation, Severity, CheckStatus
├── checks/
│   ├── protocol.py      # Check protocol + CheckContext (the run bundle)
│   ├── cutoff.py        # Check 1 — deterministic dataframe validation
│   ├── known_future.py  # Check 2 — declared-vs-used covariate diff
│   └── runtime_leak.py  # Check 3 — behavioural perturbation (the moat)
├── runner.py            # build_context + run_checks (orchestration + IO)
├── config.py            # load_spec (YAML -> validated ForecastSpec)
└── cli.py               # Click entry point: `forecastguard run`

tests/                   # pytest tiers: unit, contract, integration
examples/                # leaky -> clean demo specs and data
action.yml               # composite GitHub Action wrapping the CLI
docs/                    # PRD, ARCHITECTURE, DECISIONS, plans
```

## Non-negotiable architectural principles

1. **Nixtla-native contract (D-001).** The data shape is `unique_id` / `ds` /
   `y` by default. Column names are configurable on the spec, never hardcoded in
   a check.
2. **Behavioural over source-parsing (D-003).** The leakage check perturbs and
   diffs; it does not parse the user's source. This is what catches leaks that
   AST analysis misses and avoids false positives on correct trailing features.
3. **Check protocol + stub pattern (D-004).** Every check implements `Check` and
   depends only on `CheckContext` — never on file IO. A check ships as a stub
   first (loud SKIP) so the runner and CLI are buildable and testable before the
   logic lands. Same discipline GoldMind applies to connectors and parsers.
4. **Structured outputs everywhere (D-005).** Checks return typed `CheckResult`
   objects, never free text. The CLI renders them; the hosted tier will too.
5. **Skip loudly, never pass silently (D-006).** A missing precondition (e.g. no
   `feature_fn`) yields a prominent `SKIPPED`, not a green check.
6. **The exit code is the gate (D-007).** `fail`/`error` → exit 1. `--strict`
   promotes loud skips to failures. A clean run is the only exit 0.
7. **Honest scope.** Detects common, high-impact errors — not "all leakage."

## Testing philosophy

- **unit** — models (serialization round-trips, exit-code logic), each check's
  rule boundaries, config loading.
- **contract** — every check satisfies the `Check` protocol; the registry stays
  consistent. (The protocol analogue of GoldMind's connector parity tests.)
- **integration** — `runner.run_checks` + the CLI run end to end against a fixed
  example and produce the expected report and exit code.

Quality gates are commit-time (pre-commit: ruff + mypy + unit tier) plus the CI
workflow (`.github/workflows/ci.yml`) on push/PR.
