# Python library

Import ForecastGuard in a notebook, training script, or model-selection pipeline.
Pass a pandas DataFrame and your actual Python functions to the same engine used
by the CLI and GitHub Action. No YAML or temporary CSV is needed.

## Install

With Python 3.12 or 3.13:

```bash
python -m pip install forecastguard
# Optional real MLForecast integration:
python -m pip install 'forecastguard[nixtla]'
```

To install a development checkout instead, run `python -m pip install .`
from the repository root.

## Quickstart

```python
import pandas as pd
import forecastguard

frame = pd.DataFrame({
    "unique_id": ["A"] * 6,
    "ds": pd.date_range("2024-01-01", periods=6, freq="D"),
    "y": [1.0, 3.0, 2.0, 4.0, 6.0, 5.0],
})

def features(data):
    return data[["unique_id", "ds"]].assign(
        lag=data.groupby("unique_id")["y"].shift(1)
    )

spec = forecastguard.ForecastSpec(cutoff="2024-01-04", horizon=2, freq="D")
report = forecastguard.run_checks(spec, frame=frame, feature_fn=features)
assert report.exit_code(strict=True) == 0
```

Changing `shift(1)` to `shift(-1)` reads tomorrow's target. The runtime check
reports `FG-LEAK-001` and the strict exit code becomes `1`.

Functions can be local functions, closures, bound methods, or callable objects.
Put the preprocessing you want tested inside the function. Closures over cached
future values remain outside the interventions; a PASS only covers the supplied
data, boundaries, origins, perturbations and tolerance.

## Public entry point

```text
forecastguard.run_checks(
    spec,
    checks=None,
    *,
    frame=None,
    feature_fn=None,
    forecast_fn=None,
    pipeline_factory=None,
) -> forecastguard.Report
```

| Input | Contract |
|---|---|
| `spec` | `ForecastSpec`: column mappings, exactly one window source, horizon/frequency, covariate roles and execution settings |
| `frame` | pandas DataFrame; takes precedence over `spec.data`. When omitted, the runner loads the configured CSV/Parquet path |
| `feature_fn` | `(frame) -> DataFrame` containing identity/time columns and feature columns; compares rows before each origin |
| `forecast_fn` | `(train, future) -> DataFrame` containing identity/time columns and finite numeric predictions for the complete horizon |
| `pipeline_factory` | `() -> ReplayPipeline`, a fresh object implementing `predict(frame, cutoff, spec) -> DataFrame`; put preprocessing and fitting inside `predict` |
| `checks` | Advanced custom check sequence, with caller-managed ordering and prerequisites; omit to use the standard gate |

`ForecastSpec`, `Report`, `CheckResult`, `CheckStatus`, `Severity`, `Violation`,
`AvailabilitySpec`, `RevisionSpec`, `MLForecastAdapterSpec`, `ReplayPipeline`,
`CandidateImpact`, `RankingComparison`, `RankingAudit`, `compare_rankings`,
and `run_checks` are exported from `forecastguard`. Existing submodule imports
continue to work. Public types and keyword parameters are the supported library
surface; underscore-prefixed helpers are internal. This remains an alpha API;
pin the package version and review the changelog when upgrading.

The spec stays JSON/YAML serializable. Pass callable objects to `run_checks`,
not into the spec's string-reference fields. Supplying both a direct callable and
a reference for the same role raises `ValueError`. A pipeline factory cannot be
combined with either feature or forecast functions. Feature and forecast
functions may be used together, including a direct function for one boundary
and an import reference for the other.

The default gate validates structure and declared availability before invoking
your code. Runtime budgets apply to direct functions and factories too. Probe
inputs/outputs are copied as in CLI runs, but globals, files, models captured
outside the function, and mutable objects within dataframe cells are not process-isolated.
There is no hard wall-clock timeout.

Missing primary data, conflicting arguments, and primary file-loading problems
raise configuration/IO exceptions. Invalid contracts raise Pydantic validation
errors. Exceptions inside individual checks become typed ERROR results;
unusable or failing runtime callables can produce loud SKIPPED results.

Revision sidecars still use `RevisionSpec.data` paths. Fitted-model inspection
still uses `MLForecastAdapterSpec` import references or saved-model paths. YAML
loading requires `data`. The existing `plan_execution(spec)` API describes
file-backed, reference-configured runs; it does not plan directly supplied functions.

## Inspect and enforce results

```python
for result in report.results:
    print(result.check_id, result.status, result.detail or result.summary)
    for violation in result.violations:
        print(violation.code, violation.evidence)

print(report.model_dump_json(indent=2))
print(report.coverage, report.runtime_calls)

# In a job or command-line script:
raise SystemExit(report.exit_code(strict=True))
```

Use `exit_code(strict=True)` when every configured comparison must complete.
`report.failed` alone does not include skipped checks. Without a callable the
runtime check is SKIPPED, which strict mode blocks. The library returns a report
and never exits the process itself.

## Runnable examples

```bash
python examples/python_api/pandas_example.py
python examples/python_api/mlforecast_example.py  # requires the nixtla extra
```

The [pandas example](https://github.com/ankitlade12/ForecastGuard/blob/main/examples/python_api/pandas_example.py) checks clean/leaky
features, report round-tripping, and SARIF. The
[MLForecast example](https://github.com/ankitlade12/ForecastGuard/blob/main/examples/python_api/mlforecast_example.py) fits a real
model inside a direct forecast function across two origins with three modes,
then verifies an intentionally leaky forecast fails. Both use synthetic data in
memory and assert expected outcomes; they exit zero when those assertions pass.

For factory implementations, see the [replay contract](ADOPTION_GUIDE.md#4-fresh-pipeline-replay).
Pass your factory as `run_checks(spec, frame=frame, pipeline_factory=create_pipeline)`;
the returned object's `predict` receives the exact configured origin.

## Compare model rankings after historical replay

**Added in 0.2.0.** Install with `python -m pip install "forecastguard>=0.2.0"`.

The optional `compare_rankings` analysis compares supplied backtest predictions
with predictions from a caller-controlled historical replay. It computes pooled
and per-origin MAE, competition ranks, score/rank deltas, and winner-set changes.
Positive deltas mean worse replay performance. Exact ties share rank; a tie
appearing or disappearing changes the winner set.

*Replay* has the same meaning as the [fresh pipeline replay](ADOPTION_GUIDE.md#4-fresh-pipeline-replay)
boundary: rerunning the pipeline with only the inputs available at each origin.
`run_checks(pipeline_factory=...)` tests such a pipeline for leakage;
`compare_rankings` measures how its predictions change model selection. Here you
produce the replay predictions yourself; ForecastGuard does not execute them.

```python
from forecastguard import ForecastSpec, compare_rankings

# Both frames contain identity, time, origin, common scoring targets, and the
# same explicit prediction columns. Construct replay predictions using only
# inputs historically available at each origin, not random perturbations.
audit = compare_rankings(
    ForecastSpec(cutoff_col="origin", horizon=2, freq="D"),
    submitted=submitted_predictions,
    replay=historical_predictions,
    candidates=["model_a", "model_b"],
    replay_policy="Archived weather forecasts published by each origin; refit per origin",
)
if audit.result.status == "pass":
    overall = audit.comparisons[0]  # subsequent entries are individual origins
    print(overall.winner_changed, overall.scores)
else:
    print(audit.result.detail)  # explicit skip, no partial ranking
print(audit.model_dump_json(indent=2))
```

`RankingAudit`, `RankingComparison` and `CandidateImpact` are public typed
outputs. `RankingAudit.result` is a `CheckResult`; PASS means the comparison
completed, **not** that replay is verified or leakage-free. The analysis does not
alter `run_checks`, its three checks, or gate exit codes. Run the existing checks
on the pipelines separately. Ranking changes alone do not prove leakage.

This first version accepts materialized CV output (`cutoff_col`) only. Both
frames must have the same unique `(id, cutoff, time)` keys, identical scoring
targets and full configured horizons. Dates are parsed before alignment; row
order does not matter. Missing predictions, changed targets, invalid windows,
non-finite/non-real values and arithmetic overflow cause a loud SKIPPED result.
Window problems keep their structured `FG-CUTOFF-*` violations on `result.violations`.
The function never silently intersects evaluation rows. Series/windows missing
from **both** frames cannot be discovered without an external expected roster.

MAE gives each series/origin/horizon row equal weight; overlapping target dates
count once per origin. Because horizons are complete, each per-origin score is
also the mean of per-series MAE. MAE is scale-dependent: in panels mixing large-
and small-valued series, the large series dominate pooled rankings. If scales
differ, rescale each series identically in both frames or compare subsets of
similar scale. Results have no confidence intervals or significance
claims. The required policy description is caller-supplied provenance, not
machine-verified availability evidence. The function does not execute models,
reconstruct snapshots, or estimate a universally "corrected" backtest score.

Run the self-contained toy example, which generates predictions at two origins:

```bash
python examples/python_api/ranking_example.py
```

### Output contract

| Field | Meaning |
|---|---|
| `result` | `CheckResult`: `pass` when comparison completes; `skipped` with `detail` (plus any cutoff `violations`) when evidence is unusable |
| `replay_policy` | The supplied description, preserved verbatim; not verified |
| `compared_rows` | Number of matched evaluation rows; zero when skipped |
| `comparisons` | Pooled result first (`cutoff=None`), then origins in chronological order; empty when skipped |
| `comparisons[].rows` | Rows contributing to this comparison |
| `comparisons[].scores` | Candidate results in the requested candidate order |
| `submitted_mae`, `replay_mae` | Mean absolute error against the same scoring targets |
| `mae_delta`, `rank_delta` | Replay minus submitted; positive means worse |
| `submitted_rank`, `replay_rank` | Competition ranks, for example `1, 1, 3` for two tied winners |
| `submitted_winners`, `replay_winners` | Alphabetically sorted names of all rank-1 candidates |
| `winner_changed` | Whether the winner sets differ; does not signal every lower-rank change |
| `scope_notes` | Interpretation and coverage limitations |

Scoring uses float64 arithmetic and accurate summation. Ties use exact computed
MAE equality, with no tolerance or significance threshold. Integer inputs outside
`[-2**53, 2**53]` skip to prevent rounding from creating false ties; center or
rescale before comparison. Float inputs already rounded upstream cannot be
recovered. Use consistent timezone conventions for origins and timestamps;
naive and timezone-aware keys are not interchangeable.

Only key, target and explicitly named candidate columns are evaluated. Other
`ForecastSpec` settings (availability, revisions, callables, adapters and runtime
budgets) do not execute in this analysis. Use `run_checks` separately to validate
those contracts. `RankingAudit` has no `exit_code()` method; inspect `result.status`
before accessing comparisons. A changed winner is descriptive, not an automatic
failure of the existing gate.
