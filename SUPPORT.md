# Getting help

First check the [quickstart](README.md#try-a-working-example),
[troubleshooting guide](docs/TROUBLESHOOTING.md) and
[support matrix](SUPPORT_MATRIX.md).

For usage questions, documentation gaps and bugs, open an
[issue](https://github.com/ankitlade12/ForecastGuard/issues/new/choose).
Community support is best effort; no response-time or production support SLA is offered.

## Make a report reproducible

Include:

1. ForecastGuard and Python versions, OS, and relevant model-library versions.
2. The command, exit code, and expected versus actual result.
3. A small synthetic or anonymized CSV, YAML and callable that reproduce it.
4. Relevant violation codes and coverage entries from `--format json`.

Run `forecastguard --version` and `python --version` in the same environment used
for validation. With uv, prefix commands with `uv run` and retain any extras your
pipeline needs (for example `uv run --extra nixtla`).

Reports can contain sample data values, series identifiers, filesystem paths and
exception details. Remove private data and secrets before attaching reports or
model artifacts. Do not upload a production dataset just to reproduce a bug.

Suspected vulnerabilities belong in the private channel described in
[SECURITY.md](SECURITY.md). Conduct concerns can be reported using the contact in
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
