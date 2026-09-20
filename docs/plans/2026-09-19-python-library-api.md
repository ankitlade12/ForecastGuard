# Python library API

Reference: the user's AgentArmor library, inspected on 2026-09-19. Follow its
top-level import experience, short Python quickstart, integration extras and
release-triggered trusted publishing. ForecastGuard already uses Hatchling and
the same GitHub release/PyPI environment pattern. Keep explicit forecasting
windows and callable boundaries appropriate to this detector.

Expose `run_checks` at the package root and extend the existing runner with
keyword-only `frame`, `feature_fn`, `forecast_fn`, and `pipeline_factory` inputs.
Allow `ForecastSpec.data` to be omitted for in-memory runs. Keep callable objects
out of the serializable spec; reject duplicate reference/object declarations and
mixed replay/feature/forecast boundaries. An explicit frame takes precedence over
the data path. YAML loading continues to require a data path.

Reuse the default runner's prerequisite ordering, runtime budgets, diagnostics,
coverage, and typed Report. Direct functions must not be invoked before input
validation or when the budget blocks execution. Existing file-based calls and
explicit custom check ordering retain their behavior. Revision sidecars and
optional fitted-model inspection retain their existing file/import contracts.

Implementation sequence:

1. Add regression tests for in-memory clean/leaky runs, custom columns, direct
   forecasts/replay, ambiguity, skips, budgets, and invalid-input short-circuiting.
2. Extend the spec, context and runner; export the public entry point and replay
   protocol. Keep one check engine for Python, CLI and Action.
3. Document the API and add executable pandas/MLForecast examples.
4. Run pytest, ruff, strict mypy, build distributions, and verify a fresh wheel
   install outside the source tree with clean/leaky cases and serialized reports.

Publishing is separate release work; this change prepares the installable library.
