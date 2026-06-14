# Handoff: Slice 4 (Runtime leakage) Closed — all three checks live

**Date:** 2026-06-14
**Branch:** _(git not initialized yet — owner's choice)_
**Project root:** `/Users/ankithemantlade/Desktop/forecast_library`

## Status

Slices 1–4 are closed. **All three checks from the ForecastGuard one-pager are
implemented** to a zero-false-positive bar:

- **Cutoff integrity** (Slice 2) — deterministic dataframe validation.
- **Known-future covariates** (Slice 3) — declared-vs-used contract diff.
- **Runtime leakage** (Slice 4, the moat) — behavioural perturbation.

The product is functionally complete; remaining work is packaging/distribution
(Slice 5).

## What Landed In Slice 4

- `RuntimeLeakageCheck` (replaces the stub) in
  `forecastguard/checks/runtime_leak.py`: contract-aware future masking +
  determinism probe + pre-cutoff diff → `FG-LEAK-001`. Semantics: DECISIONS
  **D-013**.
- `feature_fn` import resolution: working dir (`runner`) + spec dir (`cli`) added
  to `sys.path`. `numpy.*` added to the mypy override.
- 10 unit tests in `tests/unit/test_runtime_leak.py` (incl. the zero-FP
  declared-future-covariate case and every loud-skip branch).
- The headline demo: `examples/runtime_leakage/` (`features.py`, `data.csv`,
  `clean.yaml`, `leaky.yaml`, README).
- Docs updated: DECISIONS D-013, `docs/plans/2026-06-14-slice-4-runtime-leakage.md`,
  ROADMAP, CHANGELOG, README, `examples/README.md`.

## Verification (fresh)

```bash
uv run pytest                                              # 53 passed
uv run ruff check forecastguard/ tests/                   # clean
uv run ruff format --check forecastguard/ tests/
uv run mypy forecastguard/                                 # Success (strict)
uv run forecastguard run --spec examples/runtime_leakage/clean.yaml   # exit 0 (all 3 PASS)
uv run forecastguard run --spec examples/runtime_leakage/leaky.yaml   # exit 1 (FG-LEAK-001 ×2)
```

All seven example specs across the four slices exit as designed.

## Open Decisions For The Owner

- **LICENSE** still intentionally absent (owner chose "no license yet").
- **git** not initialized (owner's choice); `.gitignore` + pre-commit ready.

## Next — Slice 5 (Ship)

- Harden the composite GitHub Action; add a README GIF.
- Write a Nixtla `cross_validation` tutorial PR (the GTM wedge, PRD §5).
- Choose a license; first PyPI release (the `publish.yml` trusted-publishing flow
  is ready).
