"""MLForecast fitted-model introspection without a hard runtime dependency."""

from __future__ import annotations

from typing import TYPE_CHECKING

from forecastguard.models.adapter import AdapterUsage

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    import pandas as pd

    from forecastguard.models.spec import ForecastSpec


def inspect_mlforecast(
    spec: ForecastSpec,
    frame: pd.DataFrame,
    resolve_callable: Callable[[str], Callable[..., object]],
) -> AdapterUsage:
    """Load/build a fitted MLForecast object and report raw consumed features."""
    adapter = spec.adapter
    if adapter is None:
        raise ValueError("MLForecast adapter is not configured")
    model: object
    if adapter.model_fn is not None:
        model = resolve_callable(adapter.model_fn)(frame.copy())
    else:
        model = _load_model(adapter.model_path)

    ts = getattr(model, "ts", None)
    order = getattr(ts, "features_order_", None)
    if order is None:
        raise ValueError("fitted MLForecast object has no ts.features_order_")
    feature_order = [str(value) for value in order]
    reserved = {spec.id_col, spec.time_col, spec.target_col}
    if spec.cutoff_col is not None:
        reserved.add(spec.cutoff_col)
    raw_columns = {str(value) for value in frame.columns} - reserved
    consumed = [name for name in feature_order if name in raw_columns]
    return AdapterUsage(
        adapter="mlforecast",
        consumed_covariates=list(dict.fromkeys(consumed)),
        feature_order=feature_order,
    )


def _load_model(path: Path | None) -> object:
    if path is None:
        raise ValueError("MLForecast model_path is missing")
    try:
        from mlforecast import MLForecast
    except ImportError as exc:
        raise ImportError("MLForecast adapter requires the optional 'nixtla' dependency") from exc
    return MLForecast.load(path)
