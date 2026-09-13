## What & why

Brief description of the change and the problem it solves. Link any issue and the
relevant `docs/DECISIONS.md` entry or PRD section.

## Type of change

- [ ] New check
- [ ] Bug fix
- [ ] Refactor / internal
- [ ] Docs only

## Checklist

- [ ] Tests added/updated; `make test` passes.
- [ ] `make lint` passes (ruff + mypy strict).
- [ ] Checks return typed `CheckResult`; column names read from `ctx.spec`.
- [ ] Coverage, false alarms and limitations considered (D-014).
- [ ] Relevant optional integration tests ran; changed documentation commands verified.
- [ ] `CHANGELOG.md` `[Unreleased]` updated.
- [ ] Docs updated if the spec/report contract or behavior changed.
