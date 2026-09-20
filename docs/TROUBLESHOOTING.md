# Troubleshooting

[Documentation home](README.md) · [Support](https://github.com/ankitlade12/ForecastGuard/blob/main/SUPPORT.md)

Start by running the bundled clean replay example. If it passes, compare your
spec and callable against the [configuration contracts](CONFIGURATION.md).

| Symptom | What to check |
|---|---|
| `forecastguard: command not found` | Run inside the installed environment; use `uv run forecastguard --help` from a synced checkout |
| MLForecast import error | Install `uv sync --extra nixtla` and retain `--extra nixtla` on subsequent uv commands |
| Module reference cannot import | Use `module:callable`; CLI searches the spec directory and working directory; Python callers can make modules importable or pass callable objects directly |
| Python API reports conflicting callable sources | Supply a direct function or a spec reference for each role, not both; replay cannot be combined with feature/forecast functions |
| Init refuses to write | Use a new output name; it never overwrites an existing spec or generated wrapper |
| Unattended init requests covariate roles | Supply both `--future-covariates ''` and `--static-covariates ''` if neither applies |
| Plan is READY but run fails | Plan validates data only; it does not import callables or verify runtime dependencies |
| Runtime SKIPPED because no function is configured | Add a feature function, forecast function or pipeline factory |
| Runtime SKIPPED on CV output | Supply raw history with `cutoff`/`cutoffs` to test runtime behaviour |
| Runtime budget exceeded | Inspect `plan`; explicitly adjust origins, modes or cap, accepting the corresponding coverage change |
| Nondeterministic output | Fix seeds and isolate mutable state; identical baseline inputs must produce matching outputs |
| Nullify fails but another mode detects leakage | The FAIL remains valid; inspect coverage for unsupported modes rather than assuming every probe completed |
| Empty, missing or non-finite predictions | Return unique id/time keys, all expected horizon rows, and finite numeric baseline predictions |
| Clean structural checks but runtime FAIL | A value or prediction depended on an unavailable future input; rerun with `--diagnose` |
| All checks PASS but a known leak remains | Check whether preprocessing, cached artifacts or external inputs sit outside the configured callable; consult the benchmark blind spots |
| Revision history missing | Check sidecar paths relative to the YAML and configured history columns |
| `FG-REV-003` on an older but available value | `latest_available` requires the newest published version, not any previous version |

## Diagnose one origin

```bash
uv run forecastguard run --spec examples/adoption/diagnostics.yaml \
  --origin 2024-01-06 --strict --diagnose --format json
```

This example intentionally exits `1`. The diagnostics show which individual
interventions influenced outputs. UNCHANGED means no sensitivity in that probe;
it does not clear an original failure caused by interactions among inputs.

If diagnostics skip for budget reasons, allow at least two baseline calls and
one intervention per failing component/origin, within both configured caps.
There is no automatic estimate of the backtest score inflation.

## Share a minimal reproduction

Reduce the data to a few series and relevant cutoffs while keeping the unexpected
behaviour. Include the spec, callable and exact command. Review JSON evidence for
private sample values before attaching it. See [support](https://github.com/ankitlade12/ForecastGuard/blob/main/SUPPORT.md) for the
reporting channel and environment details to include.
