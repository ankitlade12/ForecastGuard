# ForecastGuard — Project Context for Claude Code

## What This Project Is

ForecastGuard CI is an **open-source Python library, CLI and GitHub Action** that validates a
user's forecasting pipeline *before* its backtest is trusted. A model-selection
agent that ranks models by backtest score will systematically prefer the leaky
model, because leakage is what makes the backtest look best. ForecastGuard is
the guardrail that says "this backtest is inflated — don't trust it."

It runs three deliberately narrow checks against a Nixtla-native frame
(`unique_id` / `ds` / `y`):

1. **Cutoff integrity** — deterministic dataframe validation (zero false positives)
2. **Known-future covariates** — declared-vs-used contract diff
3. **Runtime leakage** — behavioural perturbation (the moat)

It is NOT a drift monitor, NOT a forecasting model-training library, NOT an "all leakage"
detector. It is a **trust gate** with an honest, narrow scope.

**Read these before starting any work, in order:**

1. `docs/ForecastGuard_PRD.md` — the canonical product spec
2. `docs/ARCHITECTURE.md` — one-page entry point, data flow, module map
3. `docs/DECISIONS.md` — engineering decisions log (D-001 …)

The PRD wins on product intent; DECISIONS wins on implementation mechanics.

## Development Methodology

Follow the **Superpowers** workflow for all non-trivial work:
Brainstorm → Spec → Plan → TDD → Implement → Review → Finalize. Plans live in
`docs/plans/` (dated). Each slice is one focused, shippable change.

## Tech Stack

- **Language:** Python 3.12 (pinned via `.python-version`), uv-managed.
- **Contract:** Pydantic v2 for all data structures (`ForecastSpec`, `Report`,
  `CheckResult`, `Violation`).
- **CLI:** Click (`forecastguard run`).
- **Data:** pandas (the dataframe checks); optional `parquet` and `nixtla` extras.
- **Config:** PyYAML (`forecastguard.yaml` → `ForecastSpec`).
- **Lint/format:** ruff. **Types:** mypy strict + pydantic plugin. **Tests:** pytest.
- **Distribution:** PyPI package + composite GitHub Action (`action.yml`).

`pyproject.toml` is the single source of truth for deps and tool config. No
`requirements.txt`.

## Architecture Principles — READ AND INTERNALIZE

(See `docs/DECISIONS.md` for the full rationale on each.)

1. **Nixtla-native contract (D-001).** Default columns `unique_id`/`ds`/`y`;
   configurable on the spec; never hardcoded in a check.
2. **Behavioural verdicts; source explanation (D-003/D-018).** Leakage status
   comes only from perturb-and-diff. AST inspection may annotate an established
   failure with a likely source line; it never creates or suppresses a verdict.
3. **Check protocol + stub pattern (D-004).** Every check implements `Check` and
   depends only on `CheckContext` — never on file IO. Ship a stub (loud SKIP)
   before the logic lands.
4. **Structured outputs everywhere (D-005).** Return typed `CheckResult`; never
   free text. Every `Violation` carries a stable `code` and an `evidence` dict.
5. **Skip loudly, never pass silently (D-006).** Missing precondition → prominent
   `SKIPPED`, not a green check.
6. **The exit code is the gate (D-007).** `fail`/`error` → exit 1; `--strict`
   promotes loud skips. Without strict mode, PASS/SKIPPED runs can exit 0.
7. **Honest, narrow scope (D-002).** Common high-impact errors, not "all leakage."

## Code Conventions (Python)

- **Package management:** uv. `uv add` for deps, `uv run` for scripts,
  `uv sync --extra dev` to set up.
- **Type hints on ALL signatures.** No `Any` unless unavoidable (pandas is the
  one tolerated source, via mypy override).
- **Docstrings on all public functions** (Google style).
- **Pydantic models for ALL data crossing a boundary** (spec, check output).
- **Use `pathlib.Path`**, not string paths.
- **Max line length 100** (ruff handles).
- **Checks never raise for expected problems** — they return a `CheckResult`.
  The runner converts unexpected exceptions into an `ERROR` result.

## Adding a New Check

1. New module in `forecastguard/checks/`, class with `check_id`, `name`, `run`.
2. Read column names from `ctx.spec` (D-001) — never hardcode.
3. Register it in `forecastguard/checks/__init__.py::default_checks`.
4. Return `CheckResult.passed/failed/skipped`; give violations stable codes.
5. Add unit tests (rule boundaries) + a contract test (protocol conformance).

## Git

- **Branches:** `feature/<slug>`. **Commits:** conventional
  (`feat:`/`fix:`/`refactor:`/`test:`/`docs:`/`chore:`). One logical change each.
- **Pre-commit gates every commit** (ruff + mypy + pytest unit). Don't
  `--no-verify` unless explicitly authorized.
- No author/coauthor tags in commit messages.

## Testing Strategy

- **unit** — models (round-trips, `exit_code` logic), each check's rule
  boundaries, config loading.
- **contract** — every check satisfies the `Check` protocol; registry stays
  consistent.
- **integration** — `run_checks` + CLI end to end on a fixed example.
- Markers registered in `pyproject.toml`; select via `uv run pytest -m <marker>`.
- No network in any tier; checks are deterministic and side-effect free.

## Self-Healing (when a build/test/lint fails)

1. **PERCEIVE** the full error; classify (import / type / test-logic / config).
2. **CONSTRUCT** 2–3 candidate root causes — don't patch the symptom.
3. **EVALUATE** the fix that addresses the root cause.
4. **COMMIT** it.
5. **VERIFY** by re-running the specific failing test + adjacent tests.
6. **RECORD** non-obvious fixes in `.claude/known_issues.md`.

## When In Doubt

1. Re-read the relevant PRD section.
2. Check `docs/DECISIONS.md` for a decision on the topic.
3. Check `.claude/known_issues.md` for prior solutions.
4. Evidence over vibes — every violation needs structured evidence; every fix
   needs verification.
