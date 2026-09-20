# ForecastGuard CI — Product Spec

**The quality gate for forecasting backtests — before a model-selection agent trusts them.**

> This is the canonical product source of truth. When the PRD and
> [`DECISIONS.md`](./DECISIONS.md) conflict: PRD wins on product intent;
> DECISIONS wins on implementation mechanics.

---

## 1. The problem

A model-selection agent watches SMAPE drop from 44 to 19, ranks that model #1,
and ships it. But the score was inflated by **future leakage** in the feature
pipeline. Automated, backtest-driven selection doesn't just *tolerate* leakage —
it **systematically prefers** the leaky model, because leakage is what makes the
backtest look best. The agent has no nose for "this 19 is a lie."

## 2. The product

An open-source **Python library, CLI and GitHub Action** that validates the *user-side*
forecasting pipeline before its backtest is trusted. Three checks, deliberately
narrow:

| Check | Catches | How |
|---|---|---|
| **Cutoff integrity** | Invalid single/rolling horizons, duplicate window keys, null IDs | Exact per-window structural validation |
| **Known-future covariates** | Invalid declarations/coverage, late availability, undeclared fitted-model inputs | Declared + framework-evidenced contract |
| **Runtime leakage** | Cross-cutoff features, unavailable exogenous use, teacher forcing | Feature and forecast-output perturbation |

### 2.1 The moat — runtime leakage

The moat is the leakage check. **A causal feature or prediction cannot change
when unavailable future inputs are perturbed.** ForecastGuard tests feature
functions before each origin and forecast functions over each horizon. An
observed change establishes future dependence behaviourally. No observed change
is bounded evidence for the tested windows, modes, data, and tolerance—not a
universal proof. Source parsing may explain a proven result, never determine it.

## 3. Why now

Everyone is wiring up agents that auto-select, auto-tune, and auto-deploy
forecasting models. The guardrail that says "this backtest is inflated — don't
let the agent pick it" doesn't exist. The adjacent tools (R competition-leak
detectors, academic leakage papers, general drift monitors) are **not** a
PR-time gate for forecasting pipelines.

## 4. Why this team

Built from direct experience operating enterprise-scale demand-forecasting
pipelines on the Nixtla stack — rolling-origin backtests, model-eligibility
logic, agentic model selection by backtest score — i.e. the exact system where
this failure mode bites. The data contract is **Nixtla-native**
(`unique_id` / `ds` / `y`) by design.

## 5. Wedge & go-to-market

- Ship **OSS CLI first** (not SaaS): 3 checks, a leaky→clean demo repo, GitHub
  Action, README GIF.
- Launch post: *"Your forecasting agent is only as good as its backtest."*
- Enter the Nixtla ecosystem the open way — community example + docs/tutorial PR
  showing ForecastGuard validating a `cross_validation` workflow. Additive to
  their CV, not a critique of it.
- Fitted MLForecast inspection and line-level explanation hints are part of the
  local alpha; additional framework adapters and hosted dashboards are later.

## 6. Honest scope

Detects **common, high-impact pipeline errors** before backtests are trusted —
not "all leakage." Requires a callable feature and/or forecast function for the
runtime check; given only a finished frame, it **skips loudly** rather than
passing silently. Materialized CV output cannot recreate raw pre-origin history.

## 7. The contract (input)

A run is driven by a typed `ForecastSpec`, created in Python or loaded from
`forecastguard.yaml` — see
[`forecastguard/models/spec.py`](https://github.com/ankitlade12/ForecastGuard/blob/main/forecastguard/models/spec.py) for the
authoritative schema. It declares:

- `data` — the long-format dataset path (one row per series × timestamp);
  Python callers may instead supply `frame` directly to `run_checks`
- `id_col` / `time_col` / `target_col` — Nixtla defaults `unique_id` / `ds` / `y`
- exactly one of `cutoff` (single raw history), `cutoffs` (rolling raw history),
  or `cutoff_col` (materialized Nixtla CV output)
- `horizon` + `freq` — the forecast window and series spacing
- `future_covariates` — what the user *declares* will be known at predict time
- optional point-in-time `availability` timestamp contracts
- optional `feature_fn`, `forecast_fn`, fitted `adapter`, perturbation modes/seed
- optional fresh `pipeline_factory`, bounded diagnostic probes, and publication-time
  `revisions` sidecars (see [adoption guide](ADOPTION_GUIDE.md))

The [Python API](PYTHON_API.md) accepts callable objects directly; YAML uses
import references. Both enter the same validation engine (D-023).

## 8. The verdict (output)

Every check returns a typed `CheckResult` (`pass` / `fail` / `skipped` /
`error`); the run aggregates them into a versioned `Report`. The CLI exits
**non-zero** when the backtest can't be trusted — that exit code is the gate.
`--strict` promotes loud skips to failures. Human, versioned JSON, SARIF 2.1.0,
GitHub annotations, and the step summary all render the same typed report.

## 9. Roadmap (slices)

| Slice | Deliverable |
|---|---|
| **1 — Foundation** | Package skeleton, Pydantic contract, Check protocol, runner, CLI, docs ✅ |
| **2** | Cutoff-integrity check (deterministic) + tests + leaky→clean example ✅ |
| **3** | Known-future covariates check (declared availability contract) ✅ |
| **4** | Runtime-leakage check (behavioural perturbation) — the moat ✅ |
| **5** | Action hardening, README asset, Nixtla tutorial, release automation ✅ locally |
| **P1–P3** | Rolling/Nixtla, MLForecast adapter, forecast perturbation, availability, evidence/benchmarks ✅ |
| **Adoption + Python API** | Setup, coverage, diagnostics, replay, revisions, and direct DataFrame/callable inputs ✅ |
| **Release** | `0.1.0` published on GitHub/PyPI; fresh registry installation verified ✅ |
| **Later** | Hosted CI tier, additional framework adapters |
