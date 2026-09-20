"""Run checks against a spec and aggregate them into a Report.

``build_context`` does the IO (load the frame, import the feature function);
``run_checks`` orchestrates the checks. A single check raising never aborts the
run — it is captured as an ``ERROR`` result.
"""

from __future__ import annotations

import importlib
import os
import sys
import traceback
from typing import TYPE_CHECKING, cast

from forecastguard.adapters import inspect_mlforecast
from forecastguard.checks import (
    CheckContext,
    RuntimeLeakageCheck,
    default_checks,
)
from forecastguard.diagnostics import diagnose
from forecastguard.execution import components, finish_coverage, initialize_coverage
from forecastguard.explain import source_hints
from forecastguard.models.execution import Diagnostic
from forecastguard.models.report import CheckResult, CheckStatus, Report
from forecastguard.replay import replay_forecast

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

    import pandas as pd

    from forecastguard.checks import Check
    from forecastguard.models.spec import ForecastSpec


def _load_frame(path: Path) -> pd.DataFrame:
    """Read the dataset from ``.csv`` or ``.parquet``."""
    import pandas as pd

    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"unsupported data format {suffix!r} for {path} (use .csv or .parquet)")


def _resolve_callable(ref: str) -> Callable[..., pd.DataFrame]:
    """Import a ``'package.module:callable'`` reference."""
    module_name, sep, attr = ref.partition(":")
    if not sep or not attr:
        raise ValueError(f"feature_fn must look like 'package.module:callable', got {ref!r}")
    # Let feature modules in the user's project (the working directory) import.
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    module = importlib.import_module(module_name)
    fn = getattr(module, attr)
    if not callable(fn):
        raise TypeError(f"feature_fn {ref!r} resolved to a non-callable")
    return cast("Callable[..., pd.DataFrame]", fn)


def _load_adapter(ctx: CheckContext) -> None:
    if ctx.spec.adapter is not None:
        try:
            ctx.adapter_usage = inspect_mlforecast(ctx.spec, ctx.frame, _resolve_callable)
        except Exception as exc:
            ctx.adapter_error = f"{type(exc).__name__}: {exc}"


def _load_callables(ctx: CheckContext) -> None:
    if ctx.spec.feature_fn:
        ctx.feature_fn = _resolve_callable(ctx.spec.feature_fn)
    if ctx.spec.forecast_fn:
        ctx.forecast_fn = _resolve_callable(ctx.spec.forecast_fn)
    if ctx.uses_pipeline:
        factory = ctx.pipeline_factory
        if factory is None:
            assert ctx.spec.pipeline_factory is not None
            factory = _resolve_callable(ctx.spec.pipeline_factory)
        ctx.forecast_fn = replay_forecast(factory, ctx.spec)


def data_context(
    spec: ForecastSpec,
    *,
    frame: pd.DataFrame | None = None,
    feature_fn: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
    forecast_fn: Callable[[pd.DataFrame, pd.DataFrame], pd.DataFrame] | None = None,
    pipeline_factory: Callable[[], object] | None = None,
) -> CheckContext:
    """Load data and revision sidecars without importing executable configuration."""
    for name, fn in (
        ("feature_fn", feature_fn),
        ("forecast_fn", forecast_fn),
        ("pipeline_factory", pipeline_factory),
    ):
        if fn is not None:
            if not callable(fn):
                raise TypeError(f"{name} must be callable")
            if getattr(spec, name) is not None:
                raise ValueError(f"{name} supplied both in spec and as a Python callable")
    if (pipeline_factory is not None or spec.pipeline_factory is not None) and (
        feature_fn is not None or forecast_fn is not None or spec.feature_fn or spec.forecast_fn
    ):
        raise ValueError("pipeline_factory is mutually exclusive with feature_fn/forecast_fn")
    if frame is None:
        if spec.data is None:
            raise ValueError("provide frame or set spec.data to a CSV/Parquet path")
        frame = _load_frame(spec.data)
    ctx = CheckContext(
        spec=spec,
        frame=frame,
        feature_fn=feature_fn,
        forecast_fn=forecast_fn,
        pipeline_factory=pipeline_factory,
    )
    for revision in spec.revisions:
        try:
            ctx.revision_frames[revision.column] = _load_frame(revision.data)
        except (OSError, ValueError, ImportError) as exc:
            ctx.revision_error = f"{revision.data}: {type(exc).__name__}: {exc}"
    initialize_coverage(ctx)
    return ctx


def build_context(spec: ForecastSpec, *, frame: pd.DataFrame | None = None) -> CheckContext:
    """Load all resources for callers managing their own check sequence."""
    ctx = data_context(spec, frame=frame)
    _load_adapter(ctx)
    _load_callables(ctx)
    _load_hints(ctx)
    return ctx


def _load_hints(ctx: CheckContext) -> None:
    if ctx.feature_fn is not None:
        ref = ctx.spec.feature_fn or str(getattr(ctx.feature_fn, "__qualname__", "feature_fn"))
        ctx.source_hints.extend(source_hints(ctx.feature_fn, ref, "feature"))
    if ctx.forecast_fn is not None and not ctx.uses_pipeline:
        ref = ctx.spec.forecast_fn or str(getattr(ctx.forecast_fn, "__qualname__", "forecast_fn"))
        ctx.source_hints.extend(source_hints(ctx.forecast_fn, ref, "forecast"))


def _run_check(check: Check, ctx: CheckContext) -> CheckResult:
    try:
        return check.run(ctx)
    except Exception:
        return CheckResult.errored(check.check_id, check.name, traceback.format_exc())


def run_checks(
    spec: ForecastSpec,
    checks: Sequence[Check] | None = None,
    *,
    frame: pd.DataFrame | None = None,
    feature_fn: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
    forecast_fn: Callable[[pd.DataFrame, pd.DataFrame], pd.DataFrame] | None = None,
    pipeline_factory: Callable[[], object] | None = None,
) -> Report:
    """Validate inputs before loading adapters or executing runtime probes.

    Args:
        spec: Validated window, covariate, and execution contract.
        checks: Optional custom sequence; retains caller ordering and prerequisites.
        frame: In-memory data, taking precedence over ``spec.data`` when supplied.
        feature_fn: Direct ``frame -> features`` callable, including local functions.
        forecast_fn: Direct ``(train, future) -> predictions`` callable.
        pipeline_factory: Fresh object factory with ``predict(frame, cutoff, spec)``.

    Returns:
        A typed report; ``report.exit_code(strict=True)`` blocks skips and failures.

    Raises:
        ValueError: Missing data or conflicting callable sources/boundaries.
        TypeError: A supplied function is not callable.
        OSError: The primary dataset cannot be read.

    Callable objects never enter the serializable spec. A direct callable and a
    spec reference for the same role are rejected. Replay cannot be combined
    with feature/forecast functions. Revision sidecars and adapters retain their
    configured file/import sources. Individual check exceptions become ERRORs.
    """
    ctx = data_context(
        spec,
        frame=frame,
        feature_fn=feature_fn,
        forecast_fn=forecast_fn,
        pipeline_factory=pipeline_factory,
    )
    if checks is not None:
        _load_adapter(ctx)
        _load_callables(ctx)
        _load_hints(ctx)
        return _report(ctx, [_run_check(check, ctx) for check in checks])

    results: list[CheckResult] = []
    for check in default_checks():
        prerequisites_pass = all(result.status is CheckStatus.PASS for result in results)
        if check.check_id == "runtime_leakage":
            result = (
                _run_runtime(ctx)
                if prerequisites_pass
                else CheckResult.skipped(
                    check.check_id,
                    check.name,
                    "input validation failed; runtime code was not loaded or executed",
                )
            )
        else:
            result = _run_check(check, ctx)
            if (
                check.check_id == "known_future_covariates"
                and prerequisites_pass
                and result.status is CheckStatus.PASS
                and spec.adapter is not None
            ):
                _load_adapter(ctx)
                result = _run_check(check, ctx)
        results.append(result)
    return _report(ctx, results)


def _report(ctx: CheckContext, results: list[CheckResult]) -> Report:
    runtime = next((result for result in results if result.check_id == "runtime_leakage"), None)
    finish_coverage(
        ctx, (runtime.detail or runtime.summary) if runtime else "runtime check not requested"
    )
    notes = [
        "Coverage includes configured origins and modes only; unconfigured origins are untested.",
        "External files, globals and caches are not isolated.",
    ]
    if not components(ctx):
        notes.append("No runtime boundary configured; only structural/availability checks ran.")
    elif not ctx.uses_pipeline:
        notes.append("Preprocessing and fitting outside configured callables are untested.")
    if ctx.spec.cutoff_col:
        notes.append("CV output has no raw training history for behavioural replay.")
    return Report(
        spec_name=ctx.spec.name,
        results=results,
        coverage=ctx.coverage,
        runtime_calls=ctx.runtime_calls,
        diagnostic_calls=ctx.diagnostic_calls,
        diagnostics=ctx.diagnostics,
        scope_notes=notes,
    )


def _run_runtime(ctx: CheckContext) -> CheckResult:
    spec = ctx.spec
    check = RuntimeLeakageCheck()
    if not components(ctx):
        return CheckResult.skipped(
            check.check_id, check.name, "no feature_fn or forecast_fn declared; no runtime coverage"
        )
    if spec.cutoff_col is not None:
        return CheckResult.skipped(
            check.check_id, check.name, "CV output has no raw history for runtime probes"
        )
    try:
        budget = check.check_budget(ctx, len(components(ctx)))
        if budget is not None:
            return budget
        _load_callables(ctx)
        result = _run_check(check, ctx)
        if spec.diagnostics and result.violations:
            try:
                diagnose(ctx, result)
            except Exception as exc:
                ctx.diagnostics.append(
                    Diagnostic(
                        component="pipeline" if ctx.uses_pipeline else "forecast",
                        cutoff="unknown",
                        status="skipped",
                        detail=f"diagnostics unavailable: {type(exc).__name__}: {exc}",
                    )
                )
        if result.violations:
            _load_hints(ctx)
            for violation in result.violations:
                component = "feature" if violation.code == "FG-LEAK-001" else "forecast"
                hints = [
                    hint.model_dump(mode="json")
                    for hint in ctx.source_hints
                    if hint.component == component
                ]
                if hints:
                    violation.evidence["source_hints"] = hints
        return result
    except Exception:
        return CheckResult.errored(check.check_id, check.name, traceback.format_exc())
