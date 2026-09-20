# Runnable examples

Run these commands from the repository root after the [source install](../README.md#try-a-working-example).
The table uses `uv run`; with a direct pip installation, use `forecastguard` instead.
Exit `1` is intentional for failure examples.

| Example | Command | Expected result |
|---|---|---|
| Python library, pandas | `uv run python examples/python_api/pandas_example.py` | Clean passes; intentional leak fails; script asserts both |
| Python library, MLForecast | `uv run --extra nixtla python examples/python_api/mlforecast_example.py` | Real rolling forecast passes; intentional leak fails |
| Clean pipeline replay | `uv run forecastguard run --spec examples/adoption/replay-clean.yaml --strict` | Exit 0; all checks pass |
| Leaky preprocessing | `uv run forecastguard run --spec examples/adoption/replay-leaky.yaml --strict` | Exit 1; `FG-FORECAST-001`, target diagnostics |
| Explain weather sensitivity | `uv run forecastguard run --spec examples/adoption/diagnostics.yaml --strict --diagnose` | Exit 1; weather changes predictions |
| Historical snapshot at an early origin | `uv run forecastguard run --spec examples/adoption/revisions.yaml --origin 2024-01-04 --strict` | Exit 0 |
| Same snapshot at all configured origins | `uv run forecastguard run --spec examples/adoption/revisions.yaml --strict` | Exit 1; `FG-REV-003` at the later origin |
| Plan without running user code | `uv run forecastguard plan --spec examples/adoption/replay-clean.yaml` | Exit 0; 10 primary calls planned |
| Clean feature function | `uv run forecastguard run --spec examples/runtime_leakage/clean.yaml --strict` | Exit 0 |
| Leaky feature function | `uv run forecastguard run --spec examples/runtime_leakage/leaky.yaml --strict` | Exit 1; `FG-LEAK-001` |
| Materialized Nixtla CV | `uv run forecastguard run --spec examples/nixtla_rolling/cv.yaml` | Exit 0 with runtime SKIPPED; strict mode would exit 1 |

The [adoption guide](../docs/ADOPTION_GUIDE.md) walks through the first five workflows.
Inspect [their pipeline implementations](adoption/pipelines.py) to see exactly
which preprocessing is inside the tested interface.

For a real fitted MLForecast integration, install the extra and run:

```bash
uv sync --extra nixtla
uv run --extra nixtla forecastguard run --spec examples/nixtla_rolling/runtime.yaml --strict
```

See the [rolling-origin tutorial](../docs/tutorials/nixtla-rolling.md) for model
inspection, CV output and repeated-fitting costs. Bundled examples use synthetic
data; the separate [feasibility benchmark](../docs/BENCHMARK_FEASIBILITY.md)
documents the external M4 subset used in its measurements.

## Additional focused examples

- [Cutoff integrity](cutoff_integrity/README.md): clean versus broken timestamp/horizon contracts.
- [Known-future covariates](known_future/README.md): valid versus inconsistent input declarations.
- [Feature leakage](runtime_leakage/README.md): causal features versus centered/full-series calculations.
- [Structural-only quickstart spec](quickstart/forecastguard.yaml): omits a runtime callable,
  so runtime SKIPPED is intentional and strict mode exits 1.
