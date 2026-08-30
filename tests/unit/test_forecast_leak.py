"""Forecast-level behavioural perturbation tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from forecastguard.checks.protocol import CheckContext
from forecastguard.checks.runtime_leak import RuntimeLeakageCheck
from forecastguard.models.report import CheckStatus
from forecastguard.models.spec import ForecastSpec

pytestmark = pytest.mark.unit


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "unique_id": ["A"] * 6 + ["B"] * 6,
            "ds": [f"2024-01-0{i}" for i in range(1, 7)] * 2,
            "y": [1.0, 2, 3, 4, 5, 6, 10.0, 20, 30, 40, 50, 60],
            "actual_temp": [10.0, 11, 12, 13, 14, 15] * 2,
            "promo": [0.0, 0, 0, 0, 1, 1] * 2,
        }
    )


def _run(
    forecast_fn: object,
    *,
    future_covariates: list[str] | None = None,
    cutoffs: list[str] | None = None,
    perturbations: list[str] | None = None,
) -> object:
    window: dict[str, object] = (
        {"cutoffs": cutoffs} if cutoffs is not None else {"cutoff": "2024-01-04"}
    )
    spec = ForecastSpec(
        data=Path("unused.csv"),
        horizon=2,
        freq="D",
        future_covariates=future_covariates or [],
        perturbations=perturbations or ["nullify"],  # type: ignore[arg-type]
        **window,
    )
    return RuntimeLeakageCheck().run(
        CheckContext(spec=spec, frame=_frame(), forecast_fn=forecast_fn)  # type: ignore[arg-type]
    )


def _clean_recursive(train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
    last = train.groupby("unique_id")["y"].last()
    out = future[["unique_id", "ds"]].copy()
    out["yhat"] = out["unique_id"].map(last)
    return out


def _uses_actual_weather(_train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
    return future[["unique_id", "ds"]].assign(yhat=future["actual_temp"])


def _teacher_forcing(_train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
    return future[["unique_id", "ds"]].assign(yhat=future["y"])


def test_clean_recursive_forecast_passes() -> None:
    result = _run(_clean_recursive)
    assert result.status is CheckStatus.PASS
    assert result.violations == []


def test_direct_actual_weather_use_fails() -> None:
    result = _run(_uses_actual_weather)
    assert result.status is CheckStatus.FAIL
    assert {violation.code for violation in result.violations} == {"FG-FORECAST-001"}
    assert result.violations[0].evidence["prediction_column"] == "yhat"


def test_holdout_teacher_forcing_fails() -> None:
    result = _run(_teacher_forcing)
    assert result.status is CheckStatus.FAIL
    assert result.violations[0].evidence["perturbation"] == "nullify"


def test_declared_planned_input_is_preserved() -> None:
    def planned(_train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
        return future[["unique_id", "ds"]].assign(yhat=future["promo"])

    result = _run(planned, future_covariates=["promo"])
    assert result.status is CheckStatus.PASS


def test_multi_window_and_all_perturbations_have_structured_evidence() -> None:
    result = _run(
        _uses_actual_weather,
        cutoffs=["2024-01-02", "2024-01-04"],
        perturbations=["nullify", "noise", "sign_flip"],
    )
    assert result.status is CheckStatus.FAIL
    assert {violation.evidence["cutoff"] for violation in result.violations} == {
        "2024-01-02T00:00:00",
        "2024-01-04T00:00:00",
    }
    assert {violation.evidence["perturbation"] for violation in result.violations} == {
        "nullify",
        "noise",
        "sign_flip",
    }


def test_nondeterministic_forecast_skips_loudly() -> None:
    counter = 0

    def nondeterministic(_train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
        nonlocal counter
        counter += 1
        return future[["unique_id", "ds"]].assign(yhat=float(counter))

    result = _run(nondeterministic)
    assert result.status is CheckStatus.SKIPPED
    assert "nondeterministic" in (result.detail or "")
