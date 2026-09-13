# Setup, planning, diagnostics, replay and historical revisions

These five features extend the same three registered checks. Existing YAML and
callables remain supported. Run from an environment with ForecastGuard installed;
repository developers can prefix commands with `uv run --no-sync`.

## 1. Guided setup

```bash
forecastguard init --data examples/adoption/data.csv --framework mlforecast
```

The prompts suggest identity/time/target columns, frequency, horizon and cutoff.
You must explicitly declare which covariates were known in advance and which are
static. Historical values and column names cannot establish availability.
Unlisted covariates remain past-only. Generated specs use all three perturbations.

For repeatable unattended setup:

```bash
forecastguard init --data examples/adoption/data.csv \
  --output /tmp/demand-guard.yaml --framework mlforecast --horizon 2 \
  --future-covariates '' --static-covariates '' --no-input
forecastguard plan --spec /tmp/demand-guard.yaml
forecastguard run --spec /tmp/demand-guard.yaml --strict
```

The command creates the YAML and a sibling `demand_guard_pipeline.py`. Existing
specs or wrappers are never overwritten. CSV and parquet inputs are supported;
parquet requires the optional parquet dependencies.

Install `uv sync --extra nixtla` from this checkout (or
`python -m pip install '.[nixtla]'`) for the generated MLForecast wrapper. Its default
is a small reference MLForecast/LinearRegression model, **not your existing
pipeline**. Connect an unfitted model factory with
`--model-factory myproject.models:create_model`; it must return a fresh MLForecast
instance. The wrapper fits identity/time/target plus explicitly declared
future/static columns, and passes only future-known columns to prediction.
Custom past-covariate transforms or other pipeline preparation need an explicit
user wrapper or the replay contract below. A generated reference model's PASS
does not validate code outside that wrapper.

`--framework python` creates only the spec; add `feature_fn`, `forecast_fn`, or
`pipeline_factory` before expecting runtime coverage. Use `--id-col`, `--time-col`,
`--target-col`, `--freq`, and `--cutoff` to override structural suggestions.

## 2. Execution planning and coverage

```bash
forecastguard plan --spec examples/adoption/replay-clean.yaml
forecastguard plan --spec examples/adoption/replay-leaky.yaml --format json
```

Planning reads datasets and revision sidecars and runs structural/availability
validation. It **never imports or executes user callables, model factories or
adapters**. READY means those static prerequisites pass; model dependencies,
importability and determinism remain unverified. A blocked plan exits 1.

For each component, primary execution count is
`origins × (2 baseline runs + number of modes)`. One replay pipeline counts as
one component; feature plus forecast functions count as two. A factory/pipeline
can perform several internal operations in one counted execution.

The plan lists the additional diagnostic cap, constrained by remaining
`max_probe_calls`. Adapter loading/fitting is additional work outside this cap.
No speculative time estimate is presented: a call-count budget is not a timeout.

Reports add these fields without changing the existing result/exit-code contract:

- `coverage`: component, cutoff, mode, status, compared row count, incomplete reason.
- `runtime_calls`: all primary plus diagnostic pipeline executions, including calls that raise.
- `diagnostic_calls`: the diagnostic subset of `runtime_calls`.
- `scope_notes`: omitted stages, unconfigured origins and external state.
- `diagnostics` and `rerun_command`: explanations and CLI reproduction instructions.

PASS/FAIL coverage means an actual comparison completed. Missing prerequisites,
nondeterminism and unsupported probes remain SKIPPED. Planning entries are
NOT_RUN. JSON preserves every entry; human output shows the first 20 plus a
completion count. GitHub summaries and SARIF retain coverage and diagnostics.
`--strict` promotes primary check skips. Optional diagnostic skips never erase
a proven failure or change the primary verdict.

## 3. Targeted failure explanations

```bash
forecastguard run --spec examples/adoption/diagnostics.yaml --strict --diagnose
forecastguard run --spec examples/adoption/diagnostics.yaml \
  --origin 2024-01-06 --strict --diagnose --format json
```

After a behavioural failure, diagnostics repeat the baseline twice and perturb
one unavailable input at a time. Reports distinguish SENSITIVE, UNCHANGED, and
SKIPPED interventions and list affected output columns and suggested
investigations. Original violations retain example rows/values.

This example identifies actual `weather` as influential while the future target
is unchanged under its individual intervention. No automatic fix is applied:
whether to lag weather, remove it, or substitute archived weather forecasts
depends on the real pipeline contract. Source hints remain possible explanations.

Enable diagnostics with `--diagnose` or `diagnostics: true`. The default
`max_diagnostic_calls` is 20. It includes the two diagnostic baseline calls per
failing boundary/origin. Diagnostics cannot exceed the remaining total
`max_probe_calls`. If fewer than three calls remain, the group skips visibly.
Input interactions can cause a primary failure without single-input sensitivity;
UNCHANGED does not clear the original failure. There is no score-inflation estimate.

`--origin` accepts only a configured raw-history cutoff. It narrows coverage and
does not imply other origins passed. CV-output selection is not supported by
this option. The CLI supplies a quoted rerun command for a failing origin.

## 4. Fresh pipeline replay

```yaml
pipeline_factory: 'myproject.pipeline:create_pipeline'
```

```python
import pandas as pd
from forecastguard import ForecastSpec

class Pipeline:
    def predict(self, frame: pd.DataFrame, cutoff: pd.Timestamp,
                spec: ForecastSpec) -> pd.DataFrame:
        # Reconstruct preprocessing and fit your model HERE using supplied data.
        # Use ds <= cutoff for training; future targets are scoring-only.
        # Return id/time keys and finite numeric horizon predictions.
        ...

def create_pipeline() -> Pipeline:
    return Pipeline()
```

Every baseline, perturbation and diagnostic execution constructs a fresh object.
Its `predict` receives copies of raw training history plus the current horizon,
the exact configured cutoff, and the spec. `pipeline_factory` is mutually
exclusive with `feature_fn`/`forecast_fn`.

```bash
forecastguard run --spec examples/adoption/replay-clean.yaml --strict
forecastguard run --spec examples/adoption/replay-leaky.yaml --strict
```

The first passes. The second fails because it recomputes a mean over training
**and future targets**; perturbing future targets changes predictions. This
exercises preprocessing inside the tested execution boundary. The same
precomputed statistic captured outside that boundary can still evade detection.

Consecutive reuse of the same pipeline object produces a loud skip. This does
not prove isolation: alternating cached instances, globals, files, frozen model
artifacts, and external services remain the user's responsibility. Replay is
in-process and includes only history plus the tested horizon, not later rows.
There is no sandbox, hard timeout, automatic cache clearing, or process reset.

## 5. Historical revision validation

```yaml
revisions:
  - column: y
    data: revisions.csv
    value_col: value
    available_at_col: available_at
    policy: latest_available
```

Sidecar columns use the spec's configured id/time names plus the declared value
and publication-time names. Paths resolve relative to the YAML file. Each
`(id, event timestamp, publication timestamp)` must identify one non-null version.

At every origin, the check selects the newest version with publication timestamp
at or before the origin. It compares that version with supplied training values.
For declared future covariates it also checks horizon inputs. Future target
values used only for scoring are excluded. Comparison uses existing numeric
tolerances (rtol 1e-5, atol 1e-8), or exact nonnumeric equality.

| Code | Meaning |
|---|---|
| `FG-REV-001` | Malformed or ambiguous version history / required columns missing |
| `FG-REV-002` | No version existed by the origin for a consumed input |
| `FG-REV-003` | Supplied value differs from the declared latest-available version |

Missing sidecar files or absent audit coverage skip loudly. Known failures remain
failures even if another contract is incomplete. CV-only target history cannot
be checked because those rows are scoring outputs, not raw training inputs.

```bash
forecastguard run --spec examples/adoption/revisions.yaml --origin 2024-01-04 --strict
forecastguard run --spec examples/adoption/revisions.yaml --strict
```

The first passes: January 1's value was 10 at the January 4 origin. The full run
fails at January 6: the history says the latest available value is now 15, while
the supplied frame still has 10. This policy requires the **latest** available
version, so it also rejects stale-but-previously-available values. It is an explicit
snapshot contract, not a universal assertion that every stale value leaks.

The check never rewrites the data. A single materialized frame may not represent
all historical vintages correctly; use origin-specific snapshots where needed.
The sidecar itself is supplied evidence, not independently verified provenance.

## Python API

```python
from forecastguard.config import load_spec
from forecastguard.planning import plan_execution
from forecastguard.runner import run_checks

spec = load_spec("forecastguard.yaml")
plan = plan_execution(spec)  # no callable imports
report = run_checks(spec)
print(report.model_dump_json(indent=2))
raise SystemExit(report.exit_code(strict=True))
```

Use importable package references in Python API specs. The CLI additionally adds
the spec directory to the import path for sibling wrapper modules.
