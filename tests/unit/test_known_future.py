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
