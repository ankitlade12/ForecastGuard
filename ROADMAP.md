# Roadmap

ForecastGuard ships in thin, independently useful slices. Status reflects the
foundation pass (2026-06-14).

## Shipped

### v0.1 — Foundation ✅
Package skeleton, typed contract, `Check` protocol + stubs, runner, Click CLI,
docs, OSS hygiene, CI + publish workflows, composite GitHub Action.

### Slice 2 — Cutoff integrity (deterministic) ✅
Duplicate `(id, ds)`, missing training history, and empty/short/misaligned
holdout vs `horizon`/`freq` — zero false positives, structured evidence per
violation (`FG-CUTOFF-*`). Shipped with a clean→broken example pair. See
DECISIONS D-011.

### Slice 3 — Known-future covariates (contract diff) ✅
Validates `spec.future_covariates` against the data: declared-but-missing column
(`FG-FUTURE-001`) and declared-but-empty-in-holdout (`FG-FUTURE-002`); undeclared
covariates surfaced as past-only. Clean→broken example pair. See DECISIONS D-012.

### Slice 4 — Runtime leakage (the moat) ✅
Behavioural perturbation: contract-aware future mask, determinism probe, re-run
`feature_fn`, diff pre-cutoff values (`FG-LEAK-001`). Forward-looking features
over *declared* future covariates are not flagged. Headline leaky→clean demo in
`examples/runtime_leakage/`. See DECISIONS D-013. **All three checks are now
implemented.**

## Next

### Slice 5 — Ship
GitHub Action hardening, README GIF, a Nixtla `cross_validation` tutorial PR.
First PyPI release. Choose a license.

## Later
- Hosted CI tier — checks on every PR, dashboards.
- MLForecast / StatsForecast adapters.
- AST hint layer — line-level explanations on top of the behavioural detector
  (an explanation aid, never the detector itself; see DECISIONS D-003/D-008).

This roadmap mirrors `docs/ForecastGuard_PRD.md` §9 and the slice plans in
`docs/plans/`.
