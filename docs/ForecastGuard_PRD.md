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

An open-source **CLI** and **GitHub Action** that validates the *user-side*
forecasting pipeline before its backtest is trusted. Three checks, deliberately
narrow:

| Check | Catches | How |
|---|---|---|
| **Cutoff integrity** | Validation rows on/before the cutoff; bad horizons; duplicate timestamps | Deterministic dataframe check — zero false positives |
| **Known-future covariates** | Variables used at predict time that won't exist in production | Declared-vs-used contract diff |
| **Runtime leakage** | Feature engineering that reads across the cutoff (centered windows, full-frame scalers) | Behavioural perturbation — not source parsing |

### 2.1 The moat — runtime leakage

The moat is the leakage check. **A leak-free feature at time `t` cannot change
when the future is hidden.** ForecastGuard re-runs the feature function on
future-masked data and diffs the pre-cutoff values. It proves leakage
*behaviourally* — catching what code-parsing misses, and never false-positiving
on a correctly-built trailing feature.

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
- **Later:** hosted CI tier (checks on every PR), MLForecast/StatsForecast
  adapters, AST hint layer for line-level explanations.

## 6. Honest scope

Detects **common, high-impact pipeline errors** before backtests are trusted —
not "all leakage." Requires a callable feature function for the runtime check;
given only a finished frame, it **skips loudly** rather than passing silently.

## 7. The contract (input)

A run is driven by a `forecastguard.yaml` spec — see
[`forecastguard/models/spec.py`](../forecastguard/models/spec.py) for the
authoritative schema. It declares:

- `data` — the long-format dataset (one row per series × timestamp)
- `id_col` / `time_col` / `target_col` — Nixtla defaults `unique_id` / `ds` / `y`
- `cutoff` — the train/validation boundary
- `horizon` + `freq` — the forecast window and series spacing
- `future_covariates` — what the user *declares* will be known at predict time
- `feature_fn` — `"package.module:callable"`, required only for the runtime check

## 8. The verdict (output)

Every check returns a typed `CheckResult` (`pass` / `fail` / `skipped` /
`error`); the run aggregates them into a `Report`. The CLI exits **non-zero**
when the backtest can't be trusted — that exit code is the gate. `--strict`
promotes loud skips to failures.

## 9. Roadmap (slices)

| Slice | Deliverable |
|---|---|
| **1 — Foundation** | Package skeleton, Pydantic contract, Check protocol + stubs, runner, CLI, docs *(this pass)* |
| **2** | Cutoff-integrity check (deterministic) + tests + leaky→clean example |
| **3** | Known-future covariates check (declared-vs-used diff) |
| **4** | Runtime-leakage check (behavioural perturbation) — the moat |
| **5** | GitHub Action hardening, README GIF, Nixtla `cross_validation` tutorial PR |
| **Later** | Hosted CI tier, MLForecast/StatsForecast adapters, AST hint layer |
