# Support matrix

This matrix describes this checkout, not a claim about every package version or
forecasting framework. Release status is in the [README](README.md).

## Environments

| Surface | Evidence | Limits |
|---|---|---|
| Python 3.12 / 3.13 on Linux | Configured [CI matrix](.github/workflows/ci.yml) | Check the workflow result for the revision you use |
| Python 3.12 on macOS ARM64 | [Recorded local benchmark](docs/BENCHMARK_FEASIBILITY.md) and local tests | Other OS/Python combinations are not established by this run |
| pandas dataframes / CSV | Core unit and integration suites | Long format, with configurable id/time/target names |
| Parquet | Loader with optional `parquet` extra | No dedicated Parquet round-trip integration test currently |
| MLForecast | Real integration tests plus generated-wrapper tests | Requires the `nixtla` extra; no guarantee for every MLForecast release |
| Other Python forecasting code | Callable and replay contract tests | Manual integration; no framework-specific compatibility claim |

Package metadata permits Python 3.12 and later; the configured CI matrix is
narrower. The [benchmark environment](docs/BENCHMARK_FEASIBILITY.md#reproduce-and-inspect)
records exact dependency versions for that measurement.

## Inputs and execution

| Feature | Supported behaviour | Evidence / limitation |
|---|---|---|
| Single raw-history cutoff | Validate all post-cutoff rows against one horizon | [Cutoff tests](tests/unit/test_cutoff.py) |
| Rolling raw history | Validate each configured origin and its bounded horizon | Same cutoff suite; later history may remain in the input |
| Materialized CV output | Validate `(id, cutoff, time)` and availability | Runtime probes skip because raw training history is absent |
| Feature callable | Compare aligned feature values before each origin | [Runtime tests](tests/unit/test_runtime_leak.py) |
| Forecast callable | Compare complete, finite numeric horizon predictions | [Forecast tests](tests/unit/test_forecast_leak.py) |
| Fresh pipeline factory | Reconstruct preprocessing/fitting inside each probe | [Replay tests](tests/integration/test_replay_diagnostics.py); external state is not isolated |
| MLForecast model inspection | Inspect consumed raw covariates on a fitted model | [Real integration](tests/integration/test_mlforecast_real.py); not an audit of all derived features |
| Generated MLForecast wrapper | Fit a reference model or a supplied unfitted factory | [Adoption tests](tests/integration/test_adoption_workflow.py); custom past-covariate transforms need a user wrapper |
| Availability timestamps | Validate declared publication times | [Availability tests](tests/unit/test_availability.py); declarations remain supplied evidence |
| Historical revisions | Enforce `latest_available` values at each origin | [Revision tests](tests/unit/test_revisions.py); stale versions also violate this policy |
| Plans and call budgets | Describe primary executions without importing user code | Adoption tests; READY does not establish importability or determinism |
| Targeted diagnostics | Single-input interventions after a proven failure | Replay/diagnostic tests; input interactions can remain unexplained |
| JSON, SARIF, GitHub summaries | Render the same typed report | [Renderer tests](tests/unit/test_render.py) and [CLI tests](tests/integration/test_cli.py) |

No built-in integrations are claimed for StatsForecast, Darts, sktime, AutoGluon,
remote model APIs or GPU training. They may be usable through the Python contracts,
but must be evaluated with their actual dependencies and runtime cost.

## Interpretation

A behavioural PASS means no sensitivity was observed for the configured data,
origin, interface, perturbations and numeric tolerance. It does not certify frozen
preprocessing, external caches, untested windows or the truth of declarations.

Runtime calls repeat model work, including fitting performed inside the callable.
There is no process isolation or hard timeout. See [benchmarks](docs/BENCHMARK_FEASIBILITY.md)
for measured costs and known misses, and [support](SUPPORT.md) to report a gap.
