# Maintainer handoff

Use the [roadmap](ROADMAP.md) for remaining work and the
[release runbook](docs/RELEASING.md) for publication. This file is a navigation
pointer, not a second backlog or a live credentials report.

## Latest verified implementation

Version [0.1.0](https://github.com/ankitlade12/ForecastGuard/releases/tag/v0.1.0)
is published on [PyPI](https://pypi.org/project/forecastguard/0.1.0/) from commit
`c4245e1`. The release workflow passed 195 tests, distribution metadata checks,
and a fresh wheel smoke test. A fresh PyPI installation passed clean/leaky Python
examples, JSON/SARIF checks and CLI version verification. Python 3.12/3.13 CI
passed before release. The Python API and README changes are merged.

The repository is public. `main` requires an approved PR, up-to-date passing
`conclude` CI, resolved conversations, and disallows force pushes/deletions,
with an administrator bypass enabled by the maintainer.
See [the branch policy](docs/CI.md#main-branch-protection).

## Next work

Add `saijasti` as a PyPI maintainer through the project collaborator settings.
Exercise the released Action in an independent consumer repository and refresh
the feasibility measurements against the release revision; see the roadmap.
