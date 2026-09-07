"""Contract tests for optional MLForecast consumed-feature introspection."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from forecastguard.adapters.mlforecast import inspect_mlforecast
from forecastguard.checks.known_future import KnownFutureCovariatesCheck
from forecastguard.checks.protocol import CheckContext
from forecastguard.models.report import CheckStatus
from forecastguard.models.spec import ForecastSpec, MLForecastAdapterSpec

pytestmark = pytest.mark.unit


def _spec(*, future_covariates: list[str] | None = None) -> ForecastSpec:
    return ForecastSpec(
        data=Path("unused.csv"),
        cutoff="2024-01-02",
        horizon=1,
        freq="D",
        future_covariates=future_covariates or [],
        adapter=MLForecastAdapterSpec(model_fn="fake:build"),
    )


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "unique_id": ["A", "A", "A"],
            "ds": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "y": [1, 2, 3],
            "actual_temp": [10, 11, 12],
            "promo": [0, 0, 1],
        }
    )


def test_adapter_intersects_mlforecast_feature_order_with_raw_columns() -> None:
    model = SimpleNamespace(
        ts=SimpleNamespace(features_order_=["lag1", "actual_temp", "promo", "dayofweek"])
    )
    usage = inspect_mlforecast(_spec(), _frame(), lambda _ref: lambda _df: model)
    assert usage.consumed_covariates == ["actual_temp", "promo"]
    assert usage.feature_order == ["lag1", "actual_temp", "promo", "dayofweek"]


def test_consumed_undeclared_raw_exogenous_feature_fails_contract() -> None:
    model = SimpleNamespace(ts=SimpleNamespace(features_order_=["lag1", "actual_temp", "promo"]))
    spec = _spec(future_covariates=["promo"])
    frame = _frame()
    usage = inspect_mlforecast(spec, frame, lambda _ref: lambda _df: model)
    result = KnownFutureCovariatesCheck().run(
        CheckContext(spec=spec, frame=frame, adapter_usage=usage)
    )
    assert result.status is CheckStatus.FAIL
    violation = next(item for item in result.violations if item.code == "FG-FUTURE-004")
    assert violation.location == "actual_temp"


def test_adapter_error_skips_loudly() -> None:
    result = KnownFutureCovariatesCheck().run(
        CheckContext(spec=_spec(), frame=_frame(), adapter_error="missing optional dependency")
    )
    assert result.status is CheckStatus.SKIPPED
    assert "missing optional dependency" in (result.detail or "")
