"""Unit tests for CutoffIntegrityCheck — the deterministic, zero-false-positive check."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from forecastguard.checks.cutoff import CutoffIntegrityCheck
from forecastguard.checks.protocol import CheckContext
from forecastguard.models.report import CheckResult, CheckStatus
from forecastguard.models.spec import ForecastSpec

pytestmark = pytest.mark.unit


def _run(
    frame: dict[str, Any], *, cutoff: str, horizon: int, freq: str = "D", **spec_kw: Any
) -> CheckResult:
    spec = ForecastSpec(
        data=Path("unused.csv"), cutoff=cutoff, horizon=horizon, freq=freq, **spec_kw
    )
    ctx = CheckContext(spec=spec, frame=pd.DataFrame(frame), feature_fn=None)
    return CutoffIntegrityCheck().run(ctx)


def _codes(result: CheckResult) -> set[str]:
    return {v.code for v in result.violations}


def _by_code(result: CheckResult, code: str) -> Any:
    return next(v for v in result.violations if v.code == code)


# --- clean cases (must PASS with zero violations) ---------------------------------


def test_clean_daily_passes() -> None:
    result = _run(
        {
            "unique_id": ["A", "A", "A", "B", "B", "B"],
            "ds": [
                "2024-01-01",
                "2024-01-02",
                "2024-01-03",
                "2024-01-01",
                "2024-01-02",
                "2024-01-03",
            ],
            "y": [1, 2, 3, 4, 5, 6],
        },
        cutoff="2024-01-02",
        horizon=1,
    )
    assert result.status is CheckStatus.PASS
    assert result.violations == []


def test_clean_monthly_passes() -> None:
    result = _run(
        {
            "unique_id": ["A", "A", "A", "A"],
            "ds": ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"],
            "y": [1, 2, 3, 4],
        },
        cutoff="2024-02-01",
        horizon=2,
        freq="MS",
    )
    assert result.status is CheckStatus.PASS


def test_custom_column_names_are_honored() -> None:
    result = _run(
        {
            "sku": ["A", "A", "A"],
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "sales": [1, 2, 3],
        },
        cutoff="2024-01-02",
        horizon=1,
        id_col="sku",
        time_col="date",
        target_col="sales",
    )
    assert result.status is CheckStatus.PASS


def test_gap_before_cutoff_is_not_a_false_positive() -> None:
    # Training has a gap (Jan 02-05 missing) but the holdout is the correct grid
    # point after the cutoff. Cutoff integrity is about the holdout, not training
    # gaps, so this must PASS.
    result = _run(
        {"unique_id": ["A", "A"], "ds": ["2024-01-01", "2024-01-06"], "y": [1, 2]},
        cutoff="2024-01-05",
        horizon=1,
    )
    assert result.status is CheckStatus.PASS
    assert result.violations == []


# --- duplicate timestamps ---------------------------------------------------------


def test_duplicate_timestamps_flagged() -> None:
    result = _run(
        {
            "unique_id": ["A", "A", "A"],
            "ds": ["2024-01-01", "2024-01-01", "2024-01-02"],
            "y": [1, 1, 2],
        },
        cutoff="2024-01-01",
        horizon=1,
    )
    assert result.status is CheckStatus.FAIL
    assert "FG-CUTOFF-001" in _codes(result)
    assert _by_code(result, "FG-CUTOFF-001").evidence["duplicate_keys"] == 1


# --- per-series structural problems ----------------------------------------------


def test_no_training_history_flagged() -> None:
    result = _run(
        {"unique_id": ["A", "A"], "ds": ["2024-01-05", "2024-01-06"], "y": [1, 2]},
        cutoff="2024-01-01",
        horizon=2,
    )
    assert _codes(result) == {"FG-CUTOFF-002"}
    assert result.status is CheckStatus.FAIL


def test_empty_holdout_flagged() -> None:
    result = _run(
        {
            "unique_id": ["A", "A", "A"],
            "ds": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "y": [1, 2, 3],
        },
        cutoff="2024-01-10",
        horizon=2,
    )
    assert _codes(result) == {"FG-CUTOFF-003"}


# --- horizon / alignment mismatches ----------------------------------------------


def test_horizon_too_few() -> None:
    result = _run(
        {
            "unique_id": ["A", "A", "A"],
            "ds": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "y": [1, 2, 3],
        },
        cutoff="2024-01-02",
        horizon=2,
    )
    v = _by_code(result, "FG-CUTOFF-004")
    assert v.evidence["reason"] == "too_few"
    assert "2024-01-04T00:00:00" in v.evidence["missing"]


def test_horizon_too_many() -> None:
    result = _run(
        {
            "unique_id": ["A", "A", "A", "A"],
            "ds": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
            "y": [1, 2, 3, 4],
        },
        cutoff="2024-01-02",
        horizon=1,
    )
    v = _by_code(result, "FG-CUTOFF-004")
    assert v.evidence["reason"] == "too_many"
    assert "2024-01-04T00:00:00" in v.evidence["unexpected"]


def test_holdout_gap_misaligned() -> None:
    # Right count (2 holdout points) but a gap: Jan-03 missing, Jan-05 extra.
    result = _run(
        {
            "unique_id": ["A", "A", "A", "A"],
            "ds": ["2024-01-01", "2024-01-02", "2024-01-04", "2024-01-05"],
            "y": [1, 2, 3, 4],
        },
        cutoff="2024-01-02",
        horizon=2,
    )
    v = _by_code(result, "FG-CUTOFF-004")
    assert v.evidence["reason"] == "misaligned"
    assert "2024-01-03T00:00:00" in v.evidence["missing"]
    assert "2024-01-05T00:00:00" in v.evidence["unexpected"]


def test_only_the_broken_series_is_flagged() -> None:
    result = _run(
        {
            "unique_id": ["A", "A", "B"],
            "ds": ["2024-01-01", "2024-01-02", "2024-01-01"],
            "y": [1, 2, 3],
        },
        cutoff="2024-01-01",
        horizon=1,
    )
    assert _codes(result) == {"FG-CUTOFF-003"}
    assert _by_code(result, "FG-CUTOFF-003").location == "B"


# --- structural guards ------------------------------------------------------------


def test_missing_time_column() -> None:
    result = _run(
        {"unique_id": ["A"], "timestamp": ["2024-01-01"], "y": [1]},
        cutoff="2024-01-01",
        horizon=1,
    )
    assert _codes(result) == {"FG-CUTOFF-010"}


def test_unparseable_timestamps() -> None:
    result = _run(
        {"unique_id": ["A", "A"], "ds": ["2024-01-01", "not-a-date"], "y": [1, 2]},
        cutoff="2024-01-01",
        horizon=1,
    )
    assert _codes(result) == {"FG-CUTOFF-011"}


def test_invalid_freq() -> None:
    result = _run(
        {"unique_id": ["A", "A"], "ds": ["2024-01-01", "2024-01-02"], "y": [1, 2]},
        cutoff="2024-01-01",
        horizon=1,
        freq="NOTAFREQ",
    )
    assert _codes(result) == {"FG-CUTOFF-012"}


def test_empty_dataset() -> None:
    result = _run({"unique_id": [], "ds": [], "y": []}, cutoff="2024-01-01", horizon=1)
    assert _codes(result) == {"FG-CUTOFF-013"}
