"""Unit tests for KnownFutureCovariatesCheck — the declared-vs-used contract diff."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from forecastguard.checks.known_future import KnownFutureCovariatesCheck
from forecastguard.checks.protocol import CheckContext
from forecastguard.models.report import CheckResult, CheckStatus
from forecastguard.models.spec import ForecastSpec

pytestmark = pytest.mark.unit


def _run(
    frame: dict[str, Any],
    *,
    cutoff: str = "2024-01-02",
    horizon: int = 1,
    freq: str = "D",
    future_covariates: list[str] | None = None,
    static_covariates: list[str] | None = None,
    **spec_kw: Any,
) -> CheckResult:
    spec = ForecastSpec(
        data=Path("unused.csv"),
        cutoff=cutoff,
        horizon=horizon,
        freq=freq,
        future_covariates=future_covariates or [],
        static_covariates=static_covariates or [],
        **spec_kw,
    )
    ctx = CheckContext(spec=spec, frame=pd.DataFrame(frame), feature_fn=None)
    return KnownFutureCovariatesCheck().run(ctx)


def _codes(result: CheckResult) -> set[str]:
    return {v.code for v in result.violations}


_BASE = {
    "unique_id": ["A", "A", "A"],
    "ds": ["2024-01-01", "2024-01-02", "2024-01-03"],
    "y": [1, 2, 3],
}


def test_clean_future_covariate_passes() -> None:
    result = _run({**_BASE, "promo": [0, 1, 1]}, future_covariates=["promo"])
    assert result.status is CheckStatus.PASS
    assert result.violations == []


def test_declared_covariate_missing_column() -> None:
    result = _run(_BASE, future_covariates=["holiday"])
    assert _codes(result) == {"FG-FUTURE-001"}
    assert result.status is CheckStatus.FAIL


def test_declared_covariate_empty_in_holdout() -> None:
    # promo is populated in train but null in the holdout row (2024-01-03).
    result = _run({**_BASE, "promo": [0, 1, None]}, future_covariates=["promo"])
    assert _codes(result) == {"FG-FUTURE-002"}
    assert result.status is CheckStatus.FAIL


def test_undeclared_covariate_is_not_a_failure() -> None:
    # `temp` is a covariate but undeclared (past-only) — must not fail.
    result = _run({**_BASE, "temp": [50, 51, 52]}, future_covariates=[])
    assert result.status is CheckStatus.PASS
    assert result.violations == []
    assert "past-only" in result.summary


def test_no_covariates_passes() -> None:
    result = _run(_BASE, future_covariates=[])
    assert result.status is CheckStatus.PASS
    assert result.violations == []


def test_static_covariate_is_excluded() -> None:
    result = _run(
        {**_BASE, "region": ["X", "X", "X"]},
        future_covariates=[],
        static_covariates=["region"],
    )
    assert result.status is CheckStatus.PASS
    assert result.violations == []
    assert "region" not in result.summary  # not treated as a dynamic covariate


def test_declared_static_covariate_must_exist() -> None:
    result = _run(_BASE, static_covariates=["region"])
    assert result.status is CheckStatus.FAIL
    assert _codes(result) == {"FG-STATIC-001"}


def test_declared_static_covariate_must_be_constant_per_series() -> None:
    result = _run(
        {**_BASE, "region": ["north", "north", "south"]},
        static_covariates=["region"],
    )
    assert result.status is CheckStatus.FAIL
    assert _codes(result) == {"FG-STATIC-002"}
    assert result.violations[0].evidence["affected_series"] == ["A"]


def test_future_covariate_requires_complete_per_series_holdout_coverage() -> None:
    result = _run(
        {
            "unique_id": ["A", "A", "A", "A", "B", "B", "B", "B"],
            "ds": [
                "2024-01-01",
                "2024-01-02",
                "2024-01-03",
                "2024-01-04",
                "2024-01-01",
                "2024-01-02",
                "2024-01-03",
                "2024-01-04",
            ],
            "y": [1, 2, 3, 4, 10, 20, 30, 40],
            "promo": [0, 0, 1, 1, 0, 0, 1, None],
        },
        cutoff="2024-01-02",
        horizon=2,
        future_covariates=["promo"],
    )
    assert result.status is CheckStatus.FAIL
    assert _codes(result) == {"FG-FUTURE-003"}
    violation = result.violations[0]
    assert violation.evidence["missing_holdout_rows"] == 1
    assert violation.evidence["affected_series"] == ["B"]


def test_multiple_violations_reported() -> None:
    result = _run({**_BASE, "promo": [0, 1, None]}, future_covariates=["promo", "holiday"])
    assert _codes(result) == {"FG-FUTURE-001", "FG-FUTURE-002"}
    assert result.status is CheckStatus.FAIL


def test_custom_column_names_are_honored() -> None:
    result = _run(
        {
            "sku": ["A", "A", "A"],
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "sales": [1, 2, 3],
            "calendar": [1, 1, 1],
        },
        future_covariates=["calendar"],
        id_col="sku",
        time_col="date",
        target_col="sales",
    )
    assert result.status is CheckStatus.PASS


def test_rolling_covariate_coverage_is_checked_per_window() -> None:
    frame = pd.DataFrame(
        {
            "unique_id": ["A"] * 6,
            "ds": [f"2024-01-0{i}" for i in range(1, 7)],
            "y": list(range(6)),
            "promo": [0, 0, 1, 1, None, 1],
        }
    )
    spec = ForecastSpec(
        data=Path("unused.csv"),
        cutoffs=["2024-01-02", "2024-01-04"],
        horizon=2,
        freq="D",
        future_covariates=["promo"],
    )
    result = KnownFutureCovariatesCheck().run(CheckContext(spec=spec, frame=frame))
    assert result.status is CheckStatus.FAIL
    assert _codes(result) == {"FG-FUTURE-003"}
    assert result.violations[0].evidence["cutoff"] == "2024-01-04T00:00:00"


def test_cv_output_covariate_coverage_uses_cutoff_column() -> None:
    frame = pd.DataFrame(
        {
            "unique_id": ["A"] * 4,
            "cutoff": ["2024-01-02"] * 2 + ["2024-01-04"] * 2,
            "ds": ["2024-01-03", "2024-01-04", "2024-01-05", "2024-01-06"],
            "y": [1, 2, 3, 4],
            "promo": [1, 1, 1, 1],
        }
    )
    spec = ForecastSpec(
        data=Path("unused.csv"),
        cutoff_col="cutoff",
        horizon=2,
        freq="D",
        future_covariates=["promo"],
    )
    result = KnownFutureCovariatesCheck().run(CheckContext(spec=spec, frame=frame))
    assert result.status is CheckStatus.PASS
