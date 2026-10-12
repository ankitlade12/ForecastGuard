# Cutoff-window performance

> Historical implementation record. Status and verification below are as of this
> plan's date; see the [current roadmap](../../ROADMAP.md) and [plan index](README.md).

## Problem

Reviewing the ranking comparison showed that `CutoffIntegrityCheck` validated an
840k-row materialized-CV frame (2,000 series x 30 origins x 14 steps) in ~38s and
800k rows of rolling raw history in ~24s. Every series/origin pair ran pandas
selection, and CV windows re-parsed the cutoff column for each pair. The D-019
scale benchmark only exercised a single cutoff, so the regression was invisible.

## Spec

Keep every verdict, violation, message, location, evidence field, ordering and
the 50-violation cap identical. Per origin, select the window rows once and prove
a series well-formed only when it has training history (raw input) and its
distinct timestamps equal the strictly increasing expected grid. Non-increasing
grids prove nothing. Suspect windows use the unchanged `_classify_window`; after
the cap, suspect windows are counted without classification. Also count those
omitted windows in the failed summary, which previously reported only 50.

## Validation

- Characterization tests pinned on `main` first: ordering across origins and
  series, truncation, rolling no-training/empty/grid violations, timezone-aware
  keys, calendar frequency and a descending grid.
- 18,000 randomized frames compared against the `main` implementation produced
  identical results across all three modes, string/datetime/timezone keys,
  categorical/int identifiers, perturbations and truncation (3,892 PASS).
- Scale: CV 840k rows ~38s -> ~1.2s; rolling 800k ~24s -> ~0.6s; single cutoff
  365k rows ~0.45s -> ~0.13s; every CV window malformed ~1.5s.
- Ruff, strict mypy and the full test suite pass.
