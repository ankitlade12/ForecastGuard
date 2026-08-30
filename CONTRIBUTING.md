# Contributing to ForecastGuard

Thanks for considering a contribution! ForecastGuard is a narrow, high-trust
gate — the bar is correctness and high-precision failures, so contributions lean on
tests and clear scope.

## Code of Conduct

This project is governed by the [Code of Conduct](CODE_OF_CONDUCT.md). By
participating, you agree to uphold it.

## How to contribute

- **Report bugs** — open an issue with the Bug Report template. A failing case
  (a small frame + spec that should fail but passes, or vice versa) is gold.
- **Suggest checks/enhancements** — open an issue with the Feature Request
  template. New checks must respect the honest-scope principle (see
  [docs/DECISIONS.md](docs/DECISIONS.md), D-002).
- **Pull requests** — welcome and reviewed.

## Branching & commits

- Branches: `feature/<slug>`, `fix/<slug>`, `docs/<slug>`, `test/<slug>`,
  `chore/<slug>`.
- Conventional commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`,
  `chore:`). One logical change per commit.

## Local development setup

Python 3.12, [uv](https://docs.astral.sh/uv/)-managed.

```bash
git clone https://github.com/ankitlade12/ForecastGuard.git
cd forecastguard
uv sync --extra dev          # create venv + install deps
uv run pre-commit install    # gate commits with ruff + mypy + unit tests

make test                    # pytest
make lint                    # ruff check + ruff format --check + mypy strict
make cli-demo                # run the CLI against examples/quickstart
```

## Adding a new check

1. Create `forecastguard/checks/<your_check>.py` with a class exposing
   `check_id`, `name`, and `run(self, ctx: CheckContext) -> CheckResult`.
2. **Read column names from `ctx.spec`** — never hardcode `unique_id`/`ds`/`y`
   (D-001).
3. **Return a `CheckResult`** (`passed` / `failed` / `skipped`); do not raise for
   an expected problem. Give every `Violation` a stable `code` and an `evidence`
   dict (D-005).
4. Register it in `forecastguard/checks/__init__.py::default_checks`.
5. Add **unit tests** (rule boundaries) and a **contract test** (protocol
   conformance). Prefer bounded claims and high-precision failures.

## Pull request checklist

- [ ] Tests added/updated and `make test` passes.
- [ ] `make lint` passes (ruff + mypy strict).
- [ ] Docs updated if behavior or the spec/report contract changed.
- [ ] `CHANGELOG.md` `[Unreleased]` updated.

Thank you!
