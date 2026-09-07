"""Optional real MLForecast adapter integration (runs with the nixtla extra)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from forecastguard.adapters.mlforecast import inspect_mlforecast
from forecastguard.config import load_spec
from forecastguard.models.report import CheckStatus
from forecastguard.models.spec import ForecastSpec, MLForecastAdapterSpec
from forecastguard.runner import run_checks

pytestmark = pytest.mark.integration


def test_real_rolling_pipeline_and_injected_leak(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("mlforecast")
    from examples.nixtla_rolling import mlforecast_tutorial as pipeline

    spec = load_spec(Path(__file__).parents[2] / "examples/nixtla_rolling/runtime.yaml")
    original = pipeline.forecast
    calls = 0

    def counted(train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
        nonlocal calls
        calls += 1
        return original(train, future)

    monkeypatch.setattr(pipeline, "forecast", counted)
    clean = run_checks(spec)
    assert clean.exit_code(strict=True) == 0
    assert calls == 6
    leaky = run_checks(
        spec.model_copy(
            update={"forecast_fn": "examples.nixtla_rolling.mlforecast_tutorial:leaky_forecast"}
        )
    )
    assert leaky.results[-1].status is CheckStatus.FAIL
    assert {v.code for v in leaky.results[-1].violations} == {"FG-FORECAST-001"}


def test_real_fitted_mlforecast_exposes_consumed_raw_exogenous_feature() -> None:
    mlforecast = pytest.importorskip("mlforecast")
    sklearn = pytest.importorskip("sklearn.linear_model")
    frame = pd.DataFrame(
        {
            "unique_id": ["A"] * 8,
            "ds": pd.date_range("2024-01-01", periods=8, freq="D"),
            "y": [float(value) for value in range(8)],
            "promo": [0.0, 0, 0, 0, 1, 1, 0, 0],
        }
    )
    model = mlforecast.MLForecast(models=sklearn.LinearRegression(), freq="D", lags=[1])
    model.fit(frame, static_features=[])
    spec = ForecastSpec(
        data=Path("unused.csv"),
        cutoff="2024-01-06",
        horizon=2,
        freq="D",
        future_covariates=["promo"],
        adapter=MLForecastAdapterSpec(model_fn="fake:factory"),
    )
    usage = inspect_mlforecast(spec, frame, lambda _ref: lambda _frame: model)
    assert "promo" in usage.consumed_covariates
