# Slice 1 — Foundation

**Date:** 2026-06-14
**Status:** Delivered (this pass)
**Goal:** Lay the project skeleton, the typed contract, and a runnable end-to-end
CLI on stubbed checks — mirroring the GoldMind project's conventions, adapted to
a CLI-tool shape.

## What this slice delivers

- **Package skeleton** — `forecastguard/` with `models/`, `checks/`, `runner.py`,
  `config.py`, `cli.py`, and a `py.typed` marker.
- **Typed contract (D-005)** — `ForecastSpec` (input) and `Report` /
  `CheckResult` / `Violation` / `Severity` / `CheckStatus` (output).
- **Check protocol + 3 stubs (D-004)** — `Check` / `CheckContext` plus
  `CutoffIntegrityCheck`, `KnownFutureCovariatesCheck`, `RuntimeLeakageCheck`,
  each returning a loud `SKIPPED`.
- **Runner** — `build_context` (load frame, import `feature_fn`) + `run_checks`
  (orchestrate, capture per-check errors).
- **CLI (D-009)** — `forecastguard run --spec ... [--strict]`, renders the report
  and exits on `Report.exit_code()` (D-007).
- **Project config** — `pyproject.toml` (single source of truth), `Makefile`,
  `.pre-commit-config.yaml`, `.python-version`, `.gitignore`.
- **Docs** — PRD, ARCHITECTURE, DECISIONS (D-001…D-010), this plan.
- **Meta** — `.claude/claude.md`, `.github/copilot-instructions.md`,
  `.github/workflows/ci.yml`, `action.yml`, `HANDOFF.md`, `README.md`.
- **Tests + example** — unit (models, exit codes) + contract (protocol) +
  integration (CLI), and `examples/quickstart` so the CLI runs out of the box.

## Acceptance (met)

- `forecastguard run --spec examples/quickstart/forecastguard.yaml` runs, prints
  three loud SKIPs, and exits `0`.
- `pytest` passes the starter tiers.
- Package imports cleanly; `models` is a self-contained Pydantic contract.

## Next slices

| Slice | Deliverable | Notes |
|---|---|---|
| **2 — Cutoff integrity** | Implement `CutoffIntegrityCheck` fully + unit tests | Deterministic; the reference impl the other checks follow. Validation-after-cutoff, horizon mismatch, duplicate `(id, ds)`. |
| **3 — Known-future covariates** | Implement `KnownFutureCovariatesCheck` | Declared-vs-used diff against `spec.future_covariates`. |
| **4 — Runtime leakage** | Implement `RuntimeLeakageCheck` (the moat, D-003) | Mask future rows, re-run `feature_fn`, diff pre-cutoff values. Build the leaky→clean `examples/` pair here. |
| **5 — Ship** | GitHub Action hardening, README GIF, Nixtla `cross_validation` tutorial PR | The GTM wedge (PRD §5). |

## Convention notes for implementers

- New check = new module in `checks/`, register in `checks.default_checks()`.
- Never hardcode column names — read them from `ctx.spec` (D-001).
- Return `CheckResult`; never raise for an expected problem (the runner turns
  unexpected exceptions into `ERROR`).
- Every `Violation` gets a stable `code` (e.g. `FG-CUTOFF-001`) and an
  `evidence` dict (D-005).
