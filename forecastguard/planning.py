"""Data-only execution plans; no imports or execution of user configuration."""

import pandas as pd
from pydantic import BaseModel, Field

from forecastguard.checks.cutoff import CutoffIntegrityCheck
from forecastguard.checks.known_future import KnownFutureCovariatesCheck
from forecastguard.execution import components
from forecastguard.models.execution import Component, ProbeCoverage
from forecastguard.models.report import CheckResult, CheckStatus
from forecastguard.models.spec import ForecastSpec
from forecastguard.runner import data_context


class ExecutionPlan(BaseModel):
    """A bounded plan, not a runtime-validation verdict."""

    schema_version: str = "1.0"
    name: str | None = None
    rows: int
    origins: list[str]
    components: list[Component]
    primary_calls: int
    diagnostic_call_limit: int
    maximum_calls: int
    budget_exceeded: bool
    ready: bool
    checks: list[CheckResult]
    coverage: list[ProbeCoverage]
    prerequisites: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def plan_execution(spec: ForecastSpec) -> ExecutionPlan:
    """Validate data, describe call budgets, and leave all callable imports untouched."""
    ctx = data_context(spec)
    checks = [CutoffIntegrityCheck().run(ctx), KnownFutureCovariatesCheck().run(ctx)]
    prerequisites = []
    try:
        origins = [cutoff.isoformat() for cutoff, _ in ctx.windows.origins]
    except (ValueError, TypeError, KeyError) as exc:
        origins = []
        prerequisites.append(f"invalid origin configuration: {exc}")
    selected = components(spec)
    calls = 0 if spec.cutoff_col else len(origins) * len(selected) * (2 + len(spec.perturbations))
    budget_exceeded = spec.max_probe_calls is not None and calls > spec.max_probe_calls
    if budget_exceeded:
        prerequisites.append(
            f"primary calls ({calls}) exceed max_probe_calls ({spec.max_probe_calls})"
        )
    if not selected:
        prerequisites.append(
            "declare feature_fn, forecast_fn, or pipeline_factory for runtime coverage"
        )
    if spec.cutoff_col:
        prerequisites.append("CV output cannot provide raw history for runtime probes")
        calls = 0
        budget_exceeded = False
    if any(check.status is not CheckStatus.PASS for check in checks):
        prerequisites.append("structural, availability, or revision validation did not pass")
    diagnostic_limit = (
        spec.max_diagnostic_calls if spec.diagnostics and selected and not spec.cutoff_col else 0
    )
    if spec.max_probe_calls is not None:
        diagnostic_limit = min(diagnostic_limit, max(0, spec.max_probe_calls - calls))
    notes = [
        "No user callables, pipeline factories or adapters were imported or executed.",
        "Callable availability, model dependencies and determinism remain unchecked.",
        "Counts are pipeline executions; a factory may perform additional internal work.",
        "Wall-clock duration is unknown; max_probe_calls is not a timeout.",
        "Coverage excludes unconfigured origins and external state.",
    ]
    if spec.adapter:
        notes.append(
            "Optional adapter loading/fitting is additional work outside the runtime call budget."
        )
    return ExecutionPlan(
        name=spec.name,
        rows=len(ctx.frame),
        origins=origins,
        components=selected,
        primary_calls=calls,
        diagnostic_call_limit=diagnostic_limit,
        maximum_calls=calls + diagnostic_limit,
        budget_exceeded=budget_exceeded,
        ready=not prerequisites,
        checks=checks,
        coverage=ctx.coverage,
        prerequisites=prerequisites,
        notes=notes,
    )


def select_origins(spec: ForecastSpec, origins: tuple[str, ...]) -> ForecastSpec:
    """Restrict a rerun to explicitly configured raw-history origins."""
    if not origins:
        return spec
    if spec.cutoff_col:
        raise ValueError("--origin requires raw-history cutoff/cutoffs input")
    declared = spec.cutoffs or ([spec.cutoff] if spec.cutoff else [])
    requested = {pd.Timestamp(value) for value in origins}
    selected = [
        value for value in declared if value is not None and pd.Timestamp(value) in requested
    ]
    if {pd.Timestamp(value) for value in selected} != requested:
        raise ValueError("--origin must match a configured cutoff")
    return spec.model_copy(update={"cutoffs": selected}) if spec.cutoffs else spec
