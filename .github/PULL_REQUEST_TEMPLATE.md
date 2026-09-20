<!-- Keep this proportional to the change. Delete inapplicable items or mark them
N/A with a reason; only check work that was actually verified. -->

## What & why

<!-- Describe the problem and resulting behavior. Include a before/after example
when useful. Link an issue and the relevant DECISIONS entry or PRD section. -->

## Type of change

- [ ] Feature / Python API
- [ ] Bug fix
- [ ] Refactor / performance
- [ ] Tests / CI / packaging
- [ ] Documentation

## Compatibility and scope

<!-- Note changes to Python signatures, YAML, report fields/codes, exit codes,
dependencies or supported environments. State breaking changes and migration
steps, or "No compatibility changes." For detector changes, describe coverage,
false-positive/negative risks and known limits; PASS is bounded evidence. -->

## Validation

<!-- List the exact commands and results. Include relevant Python/dependency
versions, optional extras, skipped checks and anything not verified.
Examples: make test; make lint; real MLForecast integration with the nixtla extra;
fresh wheel install for packaging changes; runnable examples/links for docs. -->

## Checklist

- [ ] Relevant tests added/updated and executed; results recorded above.
- [ ] Ruff lint/format and strict mypy pass for code changes.
- [ ] Relevant optional integrations ran with their extras installed.
- [ ] Public API, YAML/report compatibility and strict exit semantics considered.
- [ ] Check changes preserve typed results, `ctx.spec` column mappings, loud skips,
      and behavioral leakage verdicts.
- [ ] User-facing changes documented; changed examples and links verified.
- [ ] `CHANGELOG.md` `[Unreleased]` updated for user-visible changes.

## Review notes

<!-- Highlight any specific review concern or follow-up. Publication is a separate
maintainer action; a merged PR does not itself publish a package. -->

Merging into `main` requires one independent approval, up-to-date passing
`conclude` CI, and resolved conversations. New commits dismiss stale approvals;
these protections also apply to administrators.
