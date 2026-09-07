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
from forecastguard.explain import source_hints
from forecastguard.models.report import CheckResult, CheckStatus, Report

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
    ctx.feature_fn = _resolve_callable(ctx.spec.feature_fn) if ctx.spec.feature_fn else None
    ctx.forecast_fn = _resolve_callable(ctx.spec.forecast_fn) if ctx.spec.forecast_fn else None


def build_context(spec: ForecastSpec, *, frame: pd.DataFrame | None = None) -> CheckContext:
    """Load all resources for callers managing their own check sequence."""
    ctx = CheckContext(spec=spec, frame=_load_frame(spec.data) if frame is None else frame)
    _load_adapter(ctx)
    _load_callables(ctx)
    _load_hints(ctx)
    return ctx


def _load_hints(ctx: CheckContext) -> None:
    if ctx.feature_fn is not None and ctx.spec.feature_fn is not None:
        ctx.source_hints.extend(source_hints(ctx.feature_fn, ctx.spec.feature_fn, "feature"))
    if ctx.forecast_fn is not None and ctx.spec.forecast_fn is not None:
        ctx.source_hints.extend(source_hints(ctx.forecast_fn, ctx.spec.forecast_fn, "forecast"))


def _run_check(check: Check, ctx: CheckContext) -> CheckResult:
    try:
        return check.run(ctx)
    except Exception:
        return CheckResult.errored(check.check_id, check.name, traceback.format_exc())


def run_checks(spec: ForecastSpec, checks: Sequence[Check] | None = None) -> Report:
    """Validate inputs before loading adapters or executing runtime probes.

    Explicit custom check sequences retain the caller's execution order.
    """
    if checks is not None:
        ctx = build_context(spec)
        return Report(spec_name=spec.name, results=[_run_check(check, ctx) for check in checks])

    ctx = CheckContext(spec=spec, frame=_load_frame(spec.data))
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
    return Report(spec_name=spec.name, results=results)


def _run_runtime(ctx: CheckContext) -> CheckResult:
    spec = ctx.spec
    check = RuntimeLeakageCheck()
    if spec.feature_fn is None and spec.forecast_fn is None:
        return CheckResult.skipped(
            check.check_id, check.name, "no feature_fn or forecast_fn declared; no runtime coverage"
        )
    if spec.cutoff_col is not None:
        return CheckResult.skipped(
            check.check_id, check.name, "CV output has no raw history for runtime probes"
        )
    try:
        budget = check.check_budget(
            ctx, int(spec.feature_fn is not None) + int(spec.forecast_fn is not None)
        )
        if budget is not None:
            return budget
        _load_callables(ctx)
        result = _run_check(check, ctx)
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
