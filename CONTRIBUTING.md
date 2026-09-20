# Contributing to ForecastGuard

ForecastGuard contributions focus on reproducible behaviour, useful diagnostics
and honest coverage. Documentation fixes, minimal leakage examples and integration
reports are welcome alongside code changes.

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

For usage questions, start with [support](SUPPORT.md). Report security problems
privately using [SECURITY.md](SECURITY.md). Remove private data from reproductions.

## Branching & commits

- Branches: `feature/<slug>`, `fix/<slug>`, `docs/<slug>`, `test/<slug>`,
  `chore/<slug>`.
- Conventional commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`,
  `chore:`). One logical change per commit.
- `main` requires a PR, one approving review, up-to-date passing CI, and resolved
  conversations, including for admins. New commits dismiss prior approvals.
  Force pushes and deletion are blocked. See [branch protection](docs/CI.md#main-branch-protection).

## Local development setup

Python 3.12, [uv](https://docs.astral.sh/uv/)-managed.

```bash
git clone https://github.com/ankitlade12/ForecastGuard.git
cd ForecastGuard
uv sync --extra dev --extra nixtla
uv run pre-commit install    # gate commits with ruff + mypy + unit tests

make test                    # core pytest suite
make lint                    # ruff check + ruff format --check + mypy strict
make cli-demo                # run the clean replay example with strict gating
uv run --extra dev --extra nixtla pytest tests/integration/test_mlforecast_real.py tests/integration/test_adoption_workflow.py
```

The last command verifies the real MLForecast path and generated wrappers. Include
the `nixtla` extra on commands that need it; a plain uv sync/run may remove extras.
Once dependencies are installed, `uv run --no-sync` preserves that environment.
Core tests may skip optional integrations when their dependencies are absent.

## Documentation changes

Start with the [documentation index](docs/README.md). Keep the README focused on
the first successful run; put configuration detail in the reference guides.
Run changed commands, check relative links, and state expected nonzero exits for
intentional failures. Describe support using evidence from tests or measurements.
Do not infer compatibility from a framework name alone.

The [plan archive](docs/plans/README.md) and dated benchmark/research reports
preserve historical evidence. Label historical status clearly; use the roadmap
and current user guides for today's supported behavior and remaining work.

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
- [ ] Relevant optional integrations ran with their extras installed.
- [ ] `make lint` passes (ruff + mypy strict).
- [ ] Docs updated if behavior or the spec/report contract changed.
- [ ] `CHANGELOG.md` `[Unreleased]` updated.

Thank you!
