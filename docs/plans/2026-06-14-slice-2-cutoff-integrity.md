# Slice 2 — Cutoff integrity

> Historical implementation record. Status and verification below are as of this
> plan's date; see the [current roadmap](../../ROADMAP.md) and [plan index](README.md).

**Date:** 2026-06-14
**Status:** Delivered
**Goal:** Implement the deterministic cutoff-integrity check to a zero-false-
positive bar — the reference implementation the other two checks follow.

## Delivered

- `CutoffIntegrityCheck` (replaces the Slice-1 stub) in
  [`forecastguard/checks/cutoff.py`](../../forecastguard/checks/cutoff.py):
  structural guards, duplicate `(id, ds)` detection, and per-series train/holdout
  window validation anchored on the cutoff + `freq` grid. Semantics in
  DECISIONS **D-011**.
- 15 unit tests in
  [`tests/unit/test_cutoff.py`](../../tests/unit/test_cutoff.py) — clean (daily +
  monthly), every violation code, custom column names, and an explicit
  pre-cutoff-gap **no-false-positive** case.
- [`examples/cutoff_integrity/{clean,broken}`](../../examples/cutoff_integrity/)
  demonstrating PASS vs. a 3-violation FAIL, with a README mapping each
  corruption to its code.

## Verification (met)

- `pytest` 35/35; `ruff check` + `ruff format --check` + `mypy --strict` green.
- CLI: clean example exits `0` (Cutoff integrity **PASS**); broken example exits
  `1` (`FG-CUTOFF-001` + `-004` + `-003`).

## Semantics (summary; full detail in DECISIONS D-011)

Per series: train = `ds <= cutoff`, holdout = `ds > cutoff`. Expected holdout =
`{cutoff + k·Δ : k = 1..horizon}` at `spec.freq`. Codes `FG-CUTOFF-001..004`
(content), `-010..013` (structural guards), `-099` (overflow). Anchored on the
cutoff so pre-cutoff training gaps are not flagged.

## Next

- **Slice 3** — Known-future covariates (declared-vs-used diff).
- **Slice 4** — Runtime leakage (behavioural perturbation) + the headline
  leaky→clean demo (PRD §5 wedge).
