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
- [ ] Zero-false-positive bar considered (D-002).
- [ ] `CHANGELOG.md` `[Unreleased]` updated.
- [ ] Docs updated if the spec/report contract or behavior changed.
