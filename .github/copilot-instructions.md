# GitHub Copilot — ForecastGuard

This file mirrors `.claude/claude.md`; that file is the source of truth. Read it
in full before suggesting changes.

## TL;DR

ForecastGuard CI is an OSS **CLI + GitHub Action** that validates a Nixtla-native
forecasting pipeline (`unique_id`/`ds`/`y`) before its backtest is trusted, via
three narrow checks: **cutoff integrity**, **known-future covariates**, and
**runtime leakage** (the moat — behavioural perturbation, not source parsing).

## Hard rules

- **Read first:** `docs/ForecastGuard_PRD.md`, `docs/ARCHITECTURE.md`,
  `docs/DECISIONS.md`.
- **Structured outputs only** — checks return typed `CheckResult`, never free
  text (D-005).
- **Checks depend on `CheckContext`, never file IO** (D-004). Register new checks
  in `checks/default_checks`.
- **Never hardcode column names** — read them from `ctx.spec` (D-001).
- **Skip loudly, never pass silently** (D-006). **The exit code is the gate**
  (D-007).
- **Leakage = behaviour, not AST** (D-003).
- Python 3.12, uv-managed, Pydantic v2, ruff + mypy strict + pytest. Conventional
  commits; pre-commit gates every commit.
