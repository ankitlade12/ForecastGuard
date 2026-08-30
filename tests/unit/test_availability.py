"""Point-in-time future-covariate availability contract tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from forecastguard.checks.known_future import KnownFutureCovariatesCheck
from forecastguard.checks.protocol import CheckContext
from forecastguard.models.report import CheckStatus
from forecastguard.models.spec import AvailabilitySpec, ForecastSpec

pytestmark = pytest.mark.unit


def _spec(*, cutoffs: list[str] | None = None) -> ForecastSpec:
    source: dict[str, object] = (
        {"cutoffs": cutoffs} if cutoffs is not None else {"cutoff": "2024-01-04"}
    )
    return ForecastSpec(
        data=Path("unused.csv"),
        horizon=2,
        freq="D",
        future_covariates=["weather"],
        availability=[
            AvailabilitySpec(covariate="weather", available_at_col="weather_available_at")
        ],
        **source,
    )


def _frame(available: list[object]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "unique_id": ["A"] * 6,
            "ds": [f"2024-01-0{i}" for i in range(1, 7)],
            "y": list(range(6)),
            "weather": [10, 11, 12, 13, 14, 15],
            "weather_available_at": available,
        }
    )


def test_values_known_by_origin_pass() -> None:
    frame = _frame(
        ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-01", "2024-01-01"]
    )
    result = KnownFutureCovariatesCheck().run(CheckContext(spec=_spec(), frame=frame))
    assert result.status is CheckStatus.PASS


def test_actual_weather_unavailable_at_origin_fails() -> None:
    frame = _frame([f"2024-01-0{i}" for i in range(1, 7)])
    result = KnownFutureCovariatesCheck().run(CheckContext(spec=_spec(), frame=frame))
    assert result.status is CheckStatus.FAIL
    forecast = next(
        violation
        for violation in result.violations
        if violation.code == "FG-AVAIL-002" and violation.evidence["use_point"] == "forecast_origin"
    )
    assert forecast.evidence["cutoff"] == "2024-01-04T00:00:00"
    assert forecast.evidence["affected_rows"] == 2


def test_value_unavailable_at_historical_event_time_fails() -> None:
    frame = _frame(
        ["2024-01-02", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-01", "2024-01-01"]
    )
    result = KnownFutureCovariatesCheck().run(CheckContext(spec=_spec(), frame=frame))
    historical = next(
        violation
        for violation in result.violations
        if violation.code == "FG-AVAIL-002"
        and violation.evidence["use_point"] == "historical_event"
    )
    assert historical.evidence["affected_rows"] == 1


def test_missing_availability_column_fails() -> None:
    frame = _frame(["2024-01-01"] * 6).drop(columns="weather_available_at")
    result = KnownFutureCovariatesCheck().run(CheckContext(spec=_spec(), frame=frame))
    assert {violation.code for violation in result.violations} == {"FG-AVAIL-001"}


def test_rolling_availability_is_checked_at_every_origin() -> None:
    frame = _frame([f"2024-01-0{i}" for i in range(1, 5)] + ["2024-01-04"] * 2)
    result = KnownFutureCovariatesCheck().run(
        CheckContext(spec=_spec(cutoffs=["2024-01-02", "2024-01-04"]), frame=frame)
    )
    affected = [
        violation
        for violation in result.violations
        if violation.code == "FG-AVAIL-002" and violation.evidence["use_point"] == "forecast_origin"
    ]
    assert [violation.evidence["cutoff"] for violation in affected] == ["2024-01-02T00:00:00"]


def test_availability_contract_requires_declared_future_covariate() -> None:
    with pytest.raises(ValueError):
        ForecastSpec(
            data=Path("unused.csv"),
            cutoff="2024-01-01",
            horizon=1,
            freq="D",
            availability=[AvailabilitySpec(covariate="weather", available_at_col="available_at")],
        )
