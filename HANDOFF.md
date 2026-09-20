# Maintainer handoff

Use the [roadmap](ROADMAP.md) for remaining work and the
[release runbook](docs/RELEASING.md) for publication. This file is a navigation
pointer, not a second backlog or a live credentials report.

## Latest verified implementation

The Python library API is in [PR #4](https://github.com/ankitlade12/ForecastGuard/pull/4),
commit `ff37153`. Verification on 2026-09-19: 195 local tests passed, including
real MLForecast integration; lint, formatting and strict typing passed. Wheel
and sdist metadata, a fresh wheel installation, clean/leaky Python and CLI
examples, and JSON/SARIF reports were verified. GitHub's Python 3.12/3.13 matrix
passed for that revision. Consult the PR checks for newer revisions.

The repository is public. `main` requires an approved PR, up-to-date passing
`conclude` CI, resolved conversations, and disallows force pushes/deletions,
including for admins. See [the branch policy](docs/CI.md#main-branch-protection).

## Next work

Complete review and merge, then verify publisher configuration and prepare the
first release. GitHub authentication was working during this audit; PyPI setup
has not been verified. No release has been published by this workflow.
