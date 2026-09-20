# ForecastGuard feasibility benchmark

> Historical implementation record. Status and verification below are as of this
> plan's date; see the [current roadmap](../../ROADMAP.md) and [plan index](README.md).

## Question and scope

Assess whether the current implementation is useful as a forecasting CI gate.
Measure detection, clean-control false alarms, abstention, and execution cost.
Do not infer market demand or superiority to unexecuted competitor tools.

## Method

1. Run the existing test suite and mutation corpus.
2. Add a reproducible labelled corpus across seasonal, intermittent, and trending
   synthetic panels and multiple seeds. Include clean controls, observable leaks,
   execution-boundary blind spots, and missing-precondition cases.
3. Score FAIL as detection only for labelled leaks; ERROR/SKIPPED are abstentions,
   never true positives or clean passes. Keep expected blind spots in the results.
4. Compare structural checks, nullify runtime probes, and three-mode probes on
   identical cases. This is an ablation, not a head-to-head competitor benchmark.
5. Measure serial, warmed-up repeated real MLForecast runs at multiple panel
   sizes and origin counts. Separate gate-only from total backtest-plus-gate cost.
6. Record environment, dataset construction, raw results, timings, and limitations
   in a checked-in report. Benchmarks are local evidence, not production SLOs.

## Acceptance criteria declared before the expanded run

- At least 90% of observable seeded leaks detected with three modes.
- No failures on the curated clean controls; report skips separately.
- All configured missing-precondition probes block under strict mode.
- Representative small real-model gate completes in under 60 seconds locally.
- Report slowdown explicitly: a fivefold gate cost means approximately sixfold
  total cost when added after an existing backtest.

These are proposed pilot criteria, not statistically established guarantees.

## Implementation and validation

Write scoring tests first, add corpus and timing runner, execute serial benchmark,
review unexpected outcomes without tuning the detector to the corpus, and run
ruff, mypy, and pytest. Preserve raw false negatives and do not change production
detector semantics as part of this assessment.
