# AGENTS.md

Instructions for AI coding agents working in this repo. The authoritative,
detailed version is [`.claude/claude.md`](.claude/claude.md); this file is the
short pointer that tools reading `AGENTS.md` will find.

**Read first:** [`docs/ForecastGuard_PRD.md`](docs/ForecastGuard_PRD.md) →
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) →
[`docs/DECISIONS.md`](docs/DECISIONS.md).

**Hard rules:**
- Structured outputs only — checks return typed `CheckResult`, never free text (D-005).
- Checks depend on `CheckContext`, never file IO; register in `default_checks` (D-004).
- Never hardcode column names — read them from `ctx.spec` (D-001).
- Skip loudly, never pass silently (D-006). The exit code is the gate (D-007).
- Leakage detection is behavioural, not source-parsing (D-003).
- Python 3.12, uv, Pydantic v2, ruff + mypy strict + pytest. Conventional commits.
