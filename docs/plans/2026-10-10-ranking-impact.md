# Model-ranking impact audit

## Spec

Add an optional Python analysis comparing submitted and historical-replay CV
predictions. Both frames carry the spec's identity, timestamp, cutoff and target
columns plus explicit candidate columns. Require a materialized-CV ForecastSpec,
at least two candidates, an explicit replay policy, exact matching keys/targets,
complete horizons and finite real numeric scores. Never silently intersect rows.
The supplied target is the common scoring truth, not reconstructed training data.

Return a typed report with a CheckResult, row count, MAE/rank/deltas and winner
sets overall and per origin. Exact ties share competition rank. PASS means the
comparison completed, never that replay is leakage-free. Invalid evidence skips
with no partial scores. This is an optional analysis, not a fourth default check.
No IO, automatic repair, model execution, CLI, or statistical significance claims.

## Plan and validation

1. Add tests for a winner reversal, unchanged winner, ties, row alignment,
   renamed columns, invalid/missing evidence, numeric safety and JSON round trips.
2. Implement typed outputs and the public compare_rankings API, reusing cutoff
   validation through CheckContext.
3. Add a runnable two-origin example and Python documentation; record scope.
4. Run targeted tests, full pytest, ruff and strict mypy; review the final diff.


## Completion and follow-up review

Implemented the Python analysis and example with public typed exports. Added
README discovery, generated Sphinx API entries, output-field documentation,
release-status warnings, troubleshooting, support-matrix and catalog coverage.
CI and release workflows now run the ranking example against the installed wheel.

Review reproduced and fixed two numerical issues: row-order-sensitive sums and
large integers silently rounded to float64. Accurate summation and an explicit
integer-range skip now protect those cases, with regression tests.

Validation: 225 tests passed (30 ranking cases), Ruff checks/format and strict
mypy passed. A clean Sphinx HTML build passed with warnings treated as errors;
rendered API anchors and the included example were inspected programmatically.
Built wheel/sdist and ran ranking and existing pandas examples from an isolated
wheel installation; ranking JSON round-tripped successfully. Checks ran locally
on Python 3.12/macOS; remote Linux/Python 3.13 CI has not run in this session.
No release or deployment was performed.
