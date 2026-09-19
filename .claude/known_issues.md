# Known Issues & Non-Obvious Fixes

Accumulated across sessions. Add an entry whenever a fix wasn't obvious from the
error alone: record the **error signature** and the **resolution**.

## 2026-09-19 — Replay origins and coverage scaling

**Signature:** valid Saturday/Sunday business-day origins share the same Monday
horizon, so reconstructing the origin from the first forecast timestamp skips
both windows. Coverage bookkeeping also rescanned every requested probe for
each result, making reporting quadratic in the number of origins.

**Resolution:** pass the configured cutoff through execution to replay, including
diagnostics. Index coverage by component/origin once; regression tests verify
distinct origins and bounded entry traversal without timing-dependent assertions.

## 2026-09-12 — Missing revision history suppressed other evidence

**Signature:** with multiple revision contracts, one missing sidecar returned
SKIPPED before a successfully loaded history could report `FG-REV-003`.

**Resolution:** collect missing history as incomplete coverage, continue checking
loaded histories, and retain FAIL when any violation exists. The incomplete
reason remains in the result detail. Covered by
`test_missing_sidecar_does_not_hide_a_loaded_history_violation`.

## 2026-09-13 — Optional imports differ between mypy environments

**Signature:** the isolated pre-commit mypy environment reported an unused
`ignore[import-untyped]` on scikit-learn although the development environment
required it.

**Resolution:** use the same module-level missing-import override as the other
optional/untyped scientific dependencies and remove environment-specific inline
ignores. Verify both isolated hooks and the full development type check.
