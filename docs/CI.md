# Run ForecastGuard in CI

[Documentation home](README.md) · [CLI reference](CLI.md)

Install the same pipeline dependencies used by the backtest, make its code
importable, and run with `--strict` when runtime coverage is required. The process
exit code is the gate. Preserve reports even when validation fails.

## Workflow for this source checkout

This workflow runs a bundled example in the ForecastGuard repository and requires
no published package or Action tag. In your own project, install ForecastGuard
from a reviewed source revision alongside your model dependencies, and replace
the spec path with your pipeline's configuration.

```yaml
name: Forecast validation
on: [pull_request]
permissions:
  contents: read
jobs:
  guard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install this checkout
        run: python -m pip install .
      - name: Validate
        run: |
          forecastguard run --spec examples/adoption/replay-clean.yaml --strict --github \
            --json-output forecastguard-report.json \
            --sarif-output forecastguard-report.sarif
      - name: Preserve reports
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: forecastguard-report
          path: forecastguard-report.*
          if-no-files-found: warn
```

For MLForecast, install `'.[nixtla]'` from this checkout and any other model
dependencies before validation. For Parquet, include the `parquet` extra.
Missing reports can indicate an installation or configuration failure before
checks ran; inspect the failed step's log.

## Composite Action

[The bundled Action](../action.yml) installs ForecastGuard, runs the gate and
uploads JSON/SARIF artifacts. In this repository it can be invoked with `uses: ./`
after checkout. In another repository, use a reviewed, published source commit
of `ankitlade12/ForecastGuard`; no `v0` tag is assumed by this guide.

| Input | Default | Meaning |
|---|---|---|
| `spec` | `forecastguard.yaml` | Config path |
| `strict` | `'false'` | Set to `'true'` to require complete checks |
| `version` | Empty | Install the Action checkout; a nonempty value requests a PyPI version specifier |
| `json-output` | `forecastguard-report.json` | JSON artifact path |
| `sarif-output` | `forecastguard-report.sarif` | SARIF artifact path |
| `artifact-name` | `forecastguard-report` | Artifact upload name |

The Action sets up Python 3.12 and installs the core package. It does not provision
your model/data dependencies or install optional ForecastGuard extras. Use the
explicit CLI workflow when you need full control of environment setup. Enable
diagnostics in the YAML with `diagnostics: true`.

## Coverage, data and runtime

Use `plan` locally to inspect the call count before enabling repeated fitting in
CI. Include coverage entries in review: a selected subset of origins does not
validate the entire backtest. Optional adapter setup is outside the probe budget.

Reports contain evidence values and may include private data. Choose artifact
access and retention to suit the dataset. Treat pipeline code from pull requests
as executable code, and avoid exposing privileged credentials to untrusted code.
See [the execution policy](../SECURITY.md).

The Action uploads SARIF as an artifact; it does not submit it to GitHub code
scanning. That requires a separate upload step and appropriate repository access.

## Main branch protection

Configured on GitHub on 2026-09-19:

- Changes to `main` must go through a pull request with one approving review.
- New commits dismiss stale approvals.
- The branch must be up to date, and the `conclude` check from GitHub Actions
  must pass. It aggregates the Python 3.12/3.13 test matrix.
- Review conversations must be resolved.
- Force pushes and branch deletion are disabled.
- Repository administrators can bypass these requirements, as configured by
  the maintainer. Other contributors still require one approval and passing CI.

The PR author cannot supply their own required approval. Code-owner review is
not separately mandatory; a collaborator with write access can approve.
The repository is public. Publication of a Python package is a separate action.

GitHub settings are the enforcement mechanism; this document records the policy.
Verify the live settings before a release:

```bash
gh api repos/ankitlade12/ForecastGuard/branches/main/protection
```

See [GitHub's protected-branch documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
for the behavior of required reviews and checks.
