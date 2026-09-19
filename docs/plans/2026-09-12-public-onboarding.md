# Public onboarding and documentation

Use AgentArmor as a reference for discoverability, compatibility evidence and
community entry points. Improve ForecastGuard in this checkout; do not modify
AgentArmor or publish either repository.

## Review findings

AgentArmor links its support matrix, examples and security policy near the README
introduction, with dedicated API/integration docs and contribution instructions.

References reviewed:
- https://github.com/ankitlade12/AgentArmor
- https://github.com/ankitlade12/AgentArmor/blob/main/SUPPORT_MATRIX.md
- https://github.com/ankitlade12/AgentArmor/tree/main/docs
- https://github.com/ankitlade12/AgentArmor/blob/main/CONTRIBUTING.md

ForecastGuard needs an executable first-run path, a user documentation index,
configuration/CLI references, troubleshooting, evidence-backed support coverage,
and clearer release status. Its README advertises an unpublished PyPI package,
includes an unavailable release-tag example and stale internal milestones.

## Changes and verification

Rewrite the README around a bundled clean/leaky demo and connecting an existing
pipeline. Add reference, support and CI guides. Refresh contributor, security
and issue-reporting instructions. Include generated-wrapper integration in
optional dependency CI coverage. Keep publishing steps in a maintainer runbook.

Run documented demos and setup commands against the installed environment;
validate local documentation links and configuration snippets, verify CLI options
against help, and run relevant integration tests. No hosted documentation service,
publication or detector changes are needed for this pass.

## Outcome

Completed the README, documentation index, configuration/CLI/CI guides, examples
catalog, support matrix, troubleshooting and release runbook. Updated contributor
and security instructions, issue templates, package documentation links and the
strict demo target. Optional MLForecast CI includes generated onboarding tests.

Verification on the existing Python 3.12 environment:

- 36 CLI/adoption/real-MLForecast integration tests passed (22 upstream pandas
  deprecation warnings).
- All nine catalog commands matched their documented exit codes.
- Configuration YAML and the Python API example ran successfully.
- Unattended MLForecast generation, planning and strict execution passed.
- 137 relative links/anchors across 27 public documents resolved.
- Workflow YAML and package TOML parsed; `git diff --check` passed.

Fresh network installation, the remote GitHub workflow, repository account
settings and registry publication were not exercised. Changes remain local for
review; publication and maintainer account setup remain separate release work.
