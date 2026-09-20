# ForecastGuard feasibility assessment — 2026-09-10

## Decision

**Proceed with a limited external pilot.** The measured implementation can catch
useful forecasting leaks and run quickly on the tested small workloads. It does
not establish that an entire pipeline is free of leakage, and repeated model
fitting adds substantial relative cost. These results do not establish market
demand or superiority over another library.

Production code was left unchanged. Acceptance criteria were recorded before
the expanded run in [the benchmark plan](plans/2026-09-10-feasibility-benchmark.md).

## Detection results

The expanded corpus contains **22 pipeline patterns × 3 data regimes × 3 seeds
× 3 configurations = 594 evaluations**. Each evaluation runs against four series
of 90 daily observations, two origins, and seven-step horizons. The regimes are
seasonal, trending, and intermittent demand; seeds are 7, 19, and 41.

| Outcome per configuration | Structural checks only | Default `nullify` | All three modes |
|---|---:|---:|---:|
| Observable seeded leaks detected | 0/72 | 66/72 (91.7%) | 72/72 (100%) |
| Clean controls passed | 72/72 | 72/72 | 72/72 |
| Clean controls incorrectly failed | 0/72 | 0/72 | 0/72 |
| Execution-boundary/declaration leaks detected | 0/27 | 0/27 | 0/27 |
| All seeded leaks detected, including boundary cases | 0/99 | 66/99 (66.7%) | 72/99 (72.7%) |
| Missing/invalid callable cases blocked under strict mode | 0/27 | 27/27 | 27/27 |

The original seven-case mutation corpus also returned **7/7**. The expanded
counts represent repetitions of eight clean patterns, eight observable leak
patterns, three boundary patterns, and three execution guards. They are not
hundreds of independent real-world pipelines or a statistical estimate of
production recall. The mixed 99-case percentage depends on our chosen case mix.

The structural-only comparison intentionally excludes the runtime check. All
these frames satisfy the structural contract, so structural PASS is expected
even when a callable leaks. This is a component ablation, not a benchmark of
Pandera, Freqtrade, temporalcv, TSAuditor, or another competitor.

### What was caught

- Features using negative shifts, centered windows, full-series demeaning, and
  full-series standardization when recomputed inside the callable.
- Forecasts consuming future targets, actual future weather, or earlier actual
  values within a multistep horizon (teacher forcing).
- A prediction branch depending on whether the future target is positive.

The final branch explains all six default-mode misses. On positive seasonal
and trending panels, replacing missing targets with a positive fallback leaves
the branch unchanged. Sign flipping exposes the dependency. This demonstrates
why multiple modes can provide more evidence than nullification alone.

Clean controls cover lagged, trailing, and expanding features; known future
promotions; reordered outputs; in-place dataframe operations; and history-only
and planned-promotion forecasts. No clean control was skipped.

### What was missed

All three boundary cases produced runtime PASS in all nine panels:

1. **Frozen preprocessing:** full-series standardization happens before the
   tested function, which returns the frozen contaminated features.
2. **Cached actuals:** predictions come from future targets captured outside
   the dataframe passed to the callable.
3. **Incorrect availability:** actual future weather is falsely declared known
   future, without timestamps that could contradict that declaration.

`--strict` does not fix these cases: there is no skip to promote. Full
preprocessing must execute within the tested boundary, external data/state
must be controlled, and availability declarations need independent evidence.

Missing callables, nondeterministic forecasts, and incomplete predictions all
produced loud SKIP and blocked under strict mode. A SKIP or ERROR is counted as
an abstention, never a detected leak or a clean PASS. Three scoring tests protect
that distinction and preserve boundary misses in the overall result.

## Real-data check

The public [Nixtla MLForecast cross-validation tutorial](https://nixtlaverse.nixtla.io/mlforecast/docs/how-to-guides/cross_validation.html)
uses the M4 hourly dataset. We selected the first ten lexicographically sorted
IDs and the first 240 observations per series: **2,400 real target observations**.
Integer time indices were mapped to an artificial hourly calendar; a constant
zero `promo` column supports the existing exogenous-input interface. This does
not validate real promotion availability or original calendar metadata.

A real MLForecast/LinearRegression pipeline was evaluated over two 24-hour
origins. The leaky variant blends each prediction with its actual future target
at equal weights, deliberately halving MAE. The clean pipeline passed all three
checks; the leaky pipeline failed with `FG-FORECAST-001`. This is a seeded
failure on real data, not a newly discovered bug in MLForecast.

Clean MAE was **1,386.834**; the injected-leak MAE was **693.417**, exactly 50%
lower by construction. These are unnormalized errors on heterogeneous series,
not a claim that this small linear model is a strong M4 forecaster.

The source file's SHA-256 is
`b260c5422dfa6fc829f6a9acb2f7b43e7fac076a330e25e3a07a09fe731519b3`.
The raw artifact records the selected series IDs and exact errors.

## Runtime and memory

Final measurements are recorded in the interleaved performance artifact linked
below. Model workloads refit at every execution; linear models use lags 1, 2,
and 7. The random forest uses 20 trees, maximum depth 6, and one worker.

The following rows all use **three perturbation modes**. Times are seconds;
memory is decimal MB of peak Python allocations during the gate.

| Workload | Rows | Origins | Baseline | Additional gate | Total / baseline | Gate MB |
|---|---:|---:|---:|---:|---:|---:|
| Synthetic, linear | 2,400 | 2 | 0.060 | 0.382 | 7.41× | 0.79 |
| Synthetic, linear | 36,500 | 2 | 0.187 | 0.959 | 6.12× | 8.90 |
| Synthetic, linear | 36,500 | 5 | 0.203 | 1.221 | 7.00× | 9.06 |
| Synthetic, random forest | 2,400 | 2 | 0.142 | 0.768 | 6.41× | 0.83 |
| Real M4 subset, linear | 2,400 | 2 | 0.090 | 0.556 | 7.15× | 0.82 |

Across all nine one-/three-mode scenarios, median additional gate time ranged
from **0.236 to 1.724 seconds**, and total backtest-plus-gate cost ranged from
**4.78× to 7.41×** the baseline. All nine clean model runs passed every check;
all seven linear-model injected-leak runs failed the runtime check. The forest
was used for clean-control/cost measurement, not an additional leak injection.

Each scenario has five timed repetitions after warm-up. Baseline, full gate,
and structural-only workloads alternate with rotating order to reduce drift
from changing local load. Python allocation peaks are measured afterward in
separate untimed runs. There were no simultaneous benchmark/test jobs.

The baseline starts with in-memory, pre-split frames; the full gate includes
CSV loading and window preparation. Input generation, CSV creation, package/JIT
startup, and data download are excluded. Reported ratios are the ratio of the
sample medians; they are approximate, local measurements.

For a forecast callable, the execution budget is:

```text
ordinary backtest calls = origins
additional gate calls  = origins × (2 determinism runs + perturbation modes)
total elapsed ratio    = 1 + gate_seconds / backtest_seconds
```

Thus three modes require five additional forecast executions per origin, plus
validation overhead. A slow training job will pay that repeated training cost.
`max_probe_calls` limits the planned call count, not wall time. It skips an
oversized probe plan; strict mode then blocks it.

Cutoff-only scale measurements cover up to 1,095,000 rows. They do not measure
the full runtime gate or model fitting at that size. Memory figures represent
Python allocations observed by tracemalloc, not process RSS or native-library
memory. CPU scheduling and other local applications were not controlled.

| Cutoff-only rows | Median seconds | Median rows/second | Results |
|---|---:|---:|---|
| 36,500 | 0.068 | 535,944 | 5/5 PASS |
| 365,000 | 0.639 | 571,058 | 5/5 PASS |
| 1,095,000 | 2.502 | 437,678 | 5/5 PASS |

These measurements exceed the repository's existing 50,000-row/second cutoff
benchmark threshold. They provide no performance reason to add another
dataframe backend for this particular check.

## Pilot acceptance criteria

| Criterion declared before expanded execution | Result |
|---|---|
| At least 90% observable seeded-leak detection, three modes | PASS: 72/72 |
| No failures on curated clean controls; skips visible | PASS: 72/72 accepted, zero skips |
| All configured missing-precondition cases block with strict mode | PASS: 27/27 |
| Representative small real-model gate under 60 seconds locally | PASS: maximum scenario median 1.724 seconds |
| Explicitly report total cost and known blind spots | Above: 4.78–7.41× total cost; 27/27 boundary leaks missed |

This supports a **technical pilot**, not unconditional deployment to expensive
training workflows. Integration effort has not been measured with external
users, and no statistical population-level accuracy claim follows from this
curated corpus.

## Practical recommendation

Use the pilot configuration below when runtime validation is required:

```yaml
perturbations: [nullify, noise, sign_flip]
# Two origins and one forecast callable require ten executions:
max_probe_calls: 10
```

```bash
forecastguard run --spec forecastguard.yaml --strict
```

Choose origins explicitly based on the pipeline's relevant regimes. Omitting
origins reduces coverage; it is not equivalent to validating the full backtest.
Structural checks remain useful for inexpensive validation, but provide no
runtime assurance when the callable is omitted.

The next feasibility milestone is three independent teams' actual pipelines:
measure wrapper/configuration effort, real bugs caught, false alarms/skips,
and added training cost. Expensive models, GPU workloads, large feature
matrices, external services, revised historical data, and real GitHub runner
costs remain unmeasured. A hosted product or universal safety claim would need
substantially more evidence.

## Reproduce and inspect

Measured environment: macOS 26.5.2 ARM64, Python 3.12.12, pandas 3.0.3,
NumPy 2.4.6, Pydantic 2.13.4, MLForecast 1.0.2, scikit-learn 1.9.0.
Production HEAD: `646be654c64d1780963f8e0a6892711947ebb60d`.
At measurement time, the benchmark additions were uncommitted working-tree
files accompanying this report. The recorded HEAD identifies the measured
detector revision, not the current branch or a benchmark commit. Artifacts are
now committed; these measurements have not been rerun for the later replay,
revision and direct Python API changes.

```bash
uv sync --extra dev --extra nixtla
uv run --no-sync python -m benchmarks.feasibility_benchmark \
  --output benchmarks/results/2026-09-10-corpus.json

curl --fail --location https://datasets-nixtla.s3.amazonaws.com/m4-hourly.csv \
  --output /tmp/forecastguard-m4-hourly.csv
uv run --no-sync python -m benchmarks.feasibility_performance \
  --m4-csv /tmp/forecastguard-m4-hourly.csv \
  --output benchmarks/results/2026-09-10-performance-interleaved.json

uv run --no-sync pytest
uv run --no-sync ruff check forecastguard tests benchmarks/feasibility_benchmark.py benchmarks/feasibility_performance.py
uv run --no-sync ruff format --check forecastguard tests benchmarks/feasibility_benchmark.py benchmarks/feasibility_performance.py
uv run --no-sync mypy forecastguard tests benchmarks/feasibility_benchmark.py benchmarks/feasibility_performance.py
```

In the restricted macOS session, uv dependency resolution panicked in
`system-configuration`. The existing uv-managed environment already contained
the required packages, so measured commands used `uv run --no-sync --offline`
with `UV_CACHE_DIR=.uv-cache`. A fresh environment must install dependencies
first; `--no-sync` itself does not install them.

Artifacts:

- [Expanded corpus, all structured results (gzip JSON)](../benchmarks/results/2026-09-10-corpus.json.gz)
- [Final interleaved timings, model reports, M4 provenance, scale samples](../benchmarks/results/2026-09-10-performance-interleaved.json)
- [Initial sequential timings retained for audit](../benchmarks/results/2026-09-10-performance.json)

The corpus artifact is losslessly compressed to stay within the repository's
file-size limit. Read it with `gzip.open(path, 'rt')` and `json.load`, or decompress
it with `gzip -dk benchmarks/results/2026-09-10-corpus.json.gz`. The reproduction
command above writes the uncompressed JSON.
- [Corpus runner](../benchmarks/feasibility_benchmark.py)
- [Performance runner](../benchmarks/feasibility_performance.py)

The initial timing pass showed machine-load variation, including a three-mode
case faster than its separately measured one-mode case. It was retained and
followed by interleaved timing; the final conclusions use the latter. Neither
pass supports precise hardware-independent latency guarantees. Interleaving
reduces within-scenario drift but does not eliminate differences between
scenarios: the final five-origin linear run also showed a faster three-mode
median than its separately measured one-mode counterpart. This is timing
variability, not evidence that more probes improve speed. Raw samples are
retained rather than selecting the fastest run.
