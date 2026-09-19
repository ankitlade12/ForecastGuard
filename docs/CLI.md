# CLI and report reference

[Documentation home](README.md) · [Configuration](CONFIGURATION.md) · [Troubleshooting](TROUBLESHOOTING.md)

Use `forecastguard --help`, `forecastguard COMMAND --help`, or
`forecastguard --version`. From a uv checkout, prefix commands with `uv run`;
include `--extra nixtla` when using MLForecast, or `--no-sync` after explicitly
installing the required extras.

## Commands

| Command | Purpose | Success |
|---|---|---|
| `init --data PATH` | Write a validated YAML and optional model wrapper | Files created, exit 0 |
| `plan --spec PATH` | Validate data and describe calls without importing user code | Static requirements ready, exit 0 |
| `run --spec PATH` | Execute the configured validation checks | Exit determined by check results and strict mode |

## Init

`--data` is required. Interactive setup prompts for missing configuration.

| Options | Behaviour |
|---|---|
| `--output PATH` | YAML destination; defaults to `forecastguard.yaml` |
| `--framework python\|mlforecast` | Spec only, or spec plus wrapper; default `python` |
| `--id-col`, `--time-col`, `--target-col` | Override suggested column mappings |
| `--freq`, `--horizon`, `--cutoff` | Override structural suggestions |
| `--future-covariates`, `--static-covariates` | Explicit comma-separated roles; empty string means none |
| `--model-factory MODULE:CALLABLE` | Unfitted MLForecast factory used by the generated wrapper |
| `--no-input` | No prompts; requires horizon and explicit future/static role options |

Existing specs and wrappers are never overwritten. Python setup still needs a
runtime interface added before strict runtime validation can pass.

## Plan and run

Both accept `--spec PATH`, `--format human|json`, `--origin DATE` (repeatable),
and `--diagnose`. An origin must already be configured in a raw-history spec;
this option does not select CV rows or introduce new origins.

Plans list origins, components, primary calls, diagnostic allowance, budget
violations, prerequisites and NOT_RUN coverage. A blocked plan exits `1`.
READY does not establish callable importability, model availability or determinism.

Additional `run` options:

| Option | Behaviour |
|---|---|
| `--strict` | Treat primary check skips as failure |
| `--json-output PATH` | Also write the typed report to a file |
| `--sarif-output PATH` | Also write SARIF 2.1.0 |
| `--github` | Emit annotations and append a step summary when running on GitHub |

Output files are written to the paths supplied relative to the working directory;
create their parent directories first. Existing report files are replaced.
`--format json` keeps report stdout machine-readable; GitHub annotations go to
stderr in that mode. Configuration failures can occur before a report exists.

## Exit codes

| Condition | Exit |
|---|---|
| All checks PASS | `0` |
| Any FAIL or ERROR | `1` |
| SKIPPED with `--strict` | `1` |
| Only PASS/SKIPPED without `--strict` | `0` |
| Configuration/readiness failure | Nonzero, normally `1` |
| Invalid CLI syntax or missing required option | `2` |

Check the process exit code as well as the report. `Report.failed` excludes skips;
use `report.exit_code(strict=True)` for the strict Python API gate.

## Report contract

JSON reports carry `schema_version: "1.0"`. Consumers should tolerate additive
fields and use status/code fields rather than parsing human summaries.

| Field | Contents |
|---|---|
| `spec_name` | Optional name from the spec |
| `results` | Check ID, name, status, summary, detail and violations |
| `results[].violations` | Stable code, severity, message, location and evidence |
| `coverage` | Component, cutoff, mode, status, compared rows and incomplete reason |
| `runtime_calls` | All executed primary and diagnostic pipeline calls, including calls that raise |
| `diagnostic_calls` | Diagnostic subset of runtime calls |
| `diagnostics` | Sensitive, unchanged or skipped individual input interventions |
| `scope_notes` | Limits of this configured validation |
| `rerun_command` | CLI-generated reproduction command for a failed run, when available |

Human output limits coverage display to 20 entries; JSON retains all entries.
Optional diagnostic skips do not alter the original check verdict. SARIF includes
violations and report metadata; writing a SARIF file does not itself upload it to
GitHub code scanning. See [CI integration](CI.md).
