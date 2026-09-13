"""Shared runtime accounting and explicit configured-probe coverage."""

import pandas as pd

from forecastguard.checks.protocol import CheckContext
from forecastguard.models.execution import Component, ProbeCoverage
from forecastguard.models.spec import ForecastSpec


def components(spec: ForecastSpec) -> list[Component]:
    """List declared boundaries without importing user code."""
    if spec.pipeline_factory:
        return ["pipeline"]
    result: list[Component] = []
    if spec.feature_fn:
        result.append("feature")
    if spec.forecast_fn:
        result.append("forecast")
    return result


def initialize_coverage(ctx: CheckContext) -> None:
    """Record every configured probe before attempting execution."""
    if ctx.coverage:
        return
    selected = components(ctx.spec)
    if not selected:
        if ctx.feature_fn:
            selected.append("feature")
        if ctx.forecast_fn:
            selected.append("forecast")
    try:
        origins = [cutoff.isoformat() for cutoff, _ in ctx.windows.origins]
    except (ValueError, TypeError, KeyError):
        origins = ctx.spec.cutoffs or ([ctx.spec.cutoff] if ctx.spec.cutoff else [])
    for component in selected:
        for cutoff in origins:
            for mode in ctx.spec.perturbations:
                ctx.coverage.append(ProbeCoverage(component=component, cutoff=cutoff, mode=mode))


def mark_probe(
    ctx: CheckContext,
    component: Component,
    cutoff: pd.Timestamp,
    mode: str,
    *,
    failed: bool,
    rows: int,
) -> None:
    """Mark an actually completed comparison, independently of other modes."""
    for entry in ctx.coverage:
        if (entry.component, entry.cutoff, entry.mode) == (component, cutoff.isoformat(), mode):
            entry.status = "fail" if failed else "pass"
            entry.compared_rows = rows


def finish_coverage(
    ctx: CheckContext,
    reason: str,
    *,
    component: Component | None = None,
    cutoff: pd.Timestamp | None = None,
) -> None:
    """Keep incomplete requested comparisons visible after failed prerequisites."""
    for entry in ctx.coverage:
        if (
            entry.status == "not_run"
            and (component is None or entry.component == component)
            and (cutoff is None or entry.cutoff == cutoff.isoformat())
        ):
            entry.status = "skipped"
            entry.detail = reason


def invoke_feature(ctx: CheckContext, frame: pd.DataFrame) -> pd.DataFrame:
    """Count a feature execution even when it raises."""
    assert ctx.feature_fn is not None
    ctx.runtime_calls += 1
    return ctx.feature_fn(frame)


def invoke_forecast(ctx: CheckContext, train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
    """Count a forecast or full-pipeline execution even when it raises."""
    assert ctx.forecast_fn is not None
    ctx.runtime_calls += 1
    return ctx.forecast_fn(train, future)
