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
from forecastguard.checks import CheckContext, default_checks
from forecastguard.explain import source_hints
from forecastguard.models.report import CheckResult, Report

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


def build_context(spec: ForecastSpec) -> CheckContext:
    """Resolve a spec into a ready-to-check context (load frame, import feature_fn)."""
    frame = _load_frame(spec.data)
    feature_fn = _resolve_callable(spec.feature_fn) if spec.feature_fn else None
    forecast_fn = _resolve_callable(spec.forecast_fn) if spec.forecast_fn else None
    hints = []
    if feature_fn is not None and spec.feature_fn is not None:
        hints.extend(source_hints(feature_fn, spec.feature_fn, "feature"))
    if forecast_fn is not None and spec.forecast_fn is not None:
        hints.extend(source_hints(forecast_fn, spec.forecast_fn, "forecast"))
    adapter_usage = None
    adapter_error = None
    if spec.adapter is not None:
        try:
            adapter_usage = inspect_mlforecast(spec, frame, _resolve_callable)
        except Exception as exc:
            adapter_error = f"{type(exc).__name__}: {exc}"
    return CheckContext(
        spec=spec,
        frame=frame,
        feature_fn=feature_fn,
        forecast_fn=forecast_fn,
        adapter_usage=adapter_usage,
        adapter_error=adapter_error,
        source_hints=hints,
    )


def run_checks(spec: ForecastSpec, checks: Sequence[Check] | None = None) -> Report:
    """Run every check against the spec.

    Raises on IO/resolution problems in :func:`build_context` (a misconfigured
    spec should fail loudly); never raises for an individual check's failure.
    """
    ctx = build_context(spec)
    selected = list(checks) if checks is not None else default_checks()
    results: list[CheckResult] = []
    for check in selected:
        try:
            results.append(check.run(ctx))
        except Exception:
            results.append(CheckResult.errored(check.check_id, check.name, traceback.format_exc()))
    return Report(spec_name=spec.name, results=results)
