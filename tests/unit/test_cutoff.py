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


def test_cv_series_can_have_different_origins() -> None:
    frame = pd.DataFrame(
        {
            "unique_id": ["A", "B"],
            "ds": ["2024-01-03", "2024-01-05"],
            "cutoff": ["2024-01-02", "2024-01-04"],
            "y": [3.0, 5.0],
        }
    )
    spec = ForecastSpec(data=Path("unused.csv"), cutoff_col="cutoff", horizon=1, freq="D")
    assert (
        CutoffIntegrityCheck().run(CheckContext(spec=spec, frame=frame)).status is CheckStatus.PASS
    )


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


def test_rolling_cutoffs_allow_later_history() -> None:
    frame = {
        "unique_id": ["A"] * 8,
        "ds": [f"2024-01-0{i}" for i in range(1, 9)],
        "y": list(range(1, 9)),
    }
    spec = ForecastSpec(
        data=Path("unused.csv"),
        cutoffs=["2024-01-03", "2024-01-05"],
        horizon=2,
        freq="D",
    )
    result = CutoffIntegrityCheck().run(
        CheckContext(spec=spec, frame=pd.DataFrame(frame), feature_fn=None)
    )
    assert result.status is CheckStatus.PASS
    assert "2 window(s)" in result.summary


def test_rolling_cutoff_violation_identifies_window() -> None:
    frame = {
        "unique_id": ["A"] * 7,
        "ds": [
            "2024-01-01",
            "2024-01-02",
            "2024-01-03",
            "2024-01-04",
            "2024-01-05",
            "2024-01-07",
            "2024-01-08",
        ],
        "y": list(range(1, 8)),
    }
    spec = ForecastSpec(
        data=Path("unused.csv"),
        cutoffs=["2024-01-03", "2024-01-05"],
        horizon=2,
        freq="D",
    )
    result = CutoffIntegrityCheck().run(
        CheckContext(spec=spec, frame=pd.DataFrame(frame), feature_fn=None)
    )
    violation = _by_code(result, "FG-CUTOFF-004")
    assert violation.evidence["cutoff"] == "2024-01-05T00:00:00"
    assert "2024-01-05" in (violation.location or "")


def test_nixtla_cv_output_cutoff_column_passes() -> None:
    frame = pd.DataFrame(
        {
            "unique_id": ["A"] * 4 + ["B"] * 4,
            "cutoff": ["2024-01-02"] * 2
            + ["2024-01-04"] * 2
            + ["2024-01-02"] * 2
            + ["2024-01-04"] * 2,
            "ds": ["2024-01-03", "2024-01-04", "2024-01-05", "2024-01-06"] * 2,
            "y": list(range(8)),
        }
    )
    spec = ForecastSpec(data=Path("unused.csv"), cutoff_col="cutoff", horizon=2, freq="D")
    result = CutoffIntegrityCheck().run(CheckContext(spec=spec, frame=frame))
    assert result.status is CheckStatus.PASS
    assert "2 window(s)" in result.summary


def test_nixtla_cv_output_duplicate_triple_fails() -> None:
    frame = pd.DataFrame(
        {
            "unique_id": ["A", "A", "A"],
            "cutoff": ["2024-01-02"] * 3,
            "ds": ["2024-01-03", "2024-01-03", "2024-01-04"],
            "y": [1, 1, 2],
        }
    )
    spec = ForecastSpec(data=Path("unused.csv"), cutoff_col="cutoff", horizon=2, freq="D")
    result = CutoffIntegrityCheck().run(CheckContext(spec=spec, frame=frame))
    assert "FG-CUTOFF-001" in _codes(result)


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


def test_missing_target_column() -> None:
    result = _run(
        {"unique_id": ["A", "A"], "ds": ["2024-01-01", "2024-01-02"]},
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


def test_null_series_identifier_is_a_structural_failure() -> None:
    result = _run(
        {
            "unique_id": [None, None],
            "ds": ["2024-01-01", "2024-01-02"],
            "y": [1, 2],
        },
        cutoff="2024-01-01",
        horizon=1,
    )
    assert result.status is CheckStatus.FAIL
    assert _codes(result) == {"FG-CUTOFF-014"}
    assert _by_code(result, "FG-CUTOFF-014").evidence["null_id_rows"] == 2


# --- many windows: ordering, truncation and timestamp semantics ------------------


def _cv_frame(series: int, cutoffs: list[str], horizon: int, freq: str = "D") -> pd.DataFrame:
    rows = [
        {"unique_id": f"S{index:02d}", "cutoff": cutoff, "ds": ds, "y": 1.0}
        for index in range(series)
        for cutoff in cutoffs
        for ds in pd.date_range(cutoff, periods=horizon + 1, freq=freq)[1:]
    ]
    return pd.DataFrame(rows)


def _run_cv(frame: pd.DataFrame, *, horizon: int, freq: str = "D") -> CheckResult:
    spec = ForecastSpec(cutoff_col="cutoff", horizon=horizon, freq=freq)
    return CutoffIntegrityCheck().run(CheckContext(spec=spec, frame=frame))


def test_cv_violations_are_ordered_by_origin_then_series_and_truncated() -> None:
    first, second = "2024-01-10", "2024-01-20"
    frame = _cv_frame(60, [first, second], horizon=3)
    in_first = frame["cutoff"].eq(first)
    index = frame["unique_id"].str[1:].astype(int)
    too_few = in_first & index.mod(3).eq(0) & frame["ds"].eq(pd.Timestamp("2024-01-13"))
    misaligned = in_first & index.mod(3).eq(1) & frame["ds"].eq(pd.Timestamp("2024-01-12"))
    frame.loc[misaligned, "ds"] = pd.Timestamp("2024-01-17")
    extra = frame.loc[frame["cutoff"].eq(second) & index.lt(20)].drop_duplicates("unique_id")
    frame = pd.concat([frame.loc[~too_few], extra.assign(ds=pd.Timestamp("2024-01-25"))])

    result = _run_cv(frame, horizon=3)

    expected = [
        (f"S{i:02d}@{first}T00:00:00", "too_few" if i % 3 == 0 else "misaligned")
        for i in range(60)
        if i % 3 != 2
    ] + [(f"S{i:02d}@{second}T00:00:00", "too_many") for i in range(10)]
    *windows, overflow = result.violations
    assert result.status is CheckStatus.FAIL
    assert result.summary == "50 cutoff-integrity violations across 2 window(s)"
    assert [(v.location, v.evidence["reason"]) for v in windows] == expected
    assert {v.code for v in windows} == {"FG-CUTOFF-004"}
    assert overflow.code == "FG-CUTOFF-099"
    assert overflow.evidence == {"truncated_windows": 10}
    assert windows[0].evidence == {
        "cutoff": "2024-01-10T00:00:00",
        "reason": "too_few",
        "expected": ["2024-01-11T00:00:00", "2024-01-12T00:00:00", "2024-01-13T00:00:00"],
        "actual": ["2024-01-11T00:00:00", "2024-01-12T00:00:00"],
        "missing": ["2024-01-13T00:00:00"],
        "unexpected": [],
    }


def test_rolling_windows_report_training_holdout_and_grid_problems_in_order() -> None:
    dates = pd.date_range("2024-01-01", "2024-01-20", freq="D")
    rows = []
    for index in range(25):
        series = dates
        if index < 5:
            series = dates[dates >= "2024-01-07"]
        elif index < 10:
            series = dates[dates <= "2024-01-10"]
        elif index < 15:
            series = dates[dates != "2024-01-12"]
        rows += [{"unique_id": f"S{index:02d}", "ds": ds, "y": 1.0} for ds in series]
    spec = ForecastSpec(cutoffs=["2024-01-05", "2024-01-10", "2024-01-15"], horizon=3, freq="D")

    result = CutoffIntegrityCheck().run(CheckContext(spec=spec, frame=pd.DataFrame(rows)))

    expected = (
        [("FG-CUTOFF-002", f"S{i:02d}@2024-01-05T00:00:00") for i in range(5)]
        + [("FG-CUTOFF-003", f"S{i:02d}@2024-01-10T00:00:00") for i in range(5, 10)]
        + [("FG-CUTOFF-004", f"S{i:02d}@2024-01-10T00:00:00") for i in range(10, 15)]
        + [("FG-CUTOFF-003", f"S{i:02d}@2024-01-15T00:00:00") for i in range(5, 10)]
    )
    assert [(v.code, v.location) for v in result.violations] == expected
    assert result.summary == "20 cutoff-integrity violations across 3 window(s)"


def test_timezone_aware_cv_keys_are_validated() -> None:
    frame = _cv_frame(3, ["2024-01-10T00:00:00+00:00"], horizon=2)
    assert _run_cv(frame, horizon=2).status is CheckStatus.PASS
    frame.loc[0, "ds"] = pd.Timestamp("2024-01-15T00:00:00+00:00")
    result = _run_cv(frame, horizon=2)
    assert [v.location for v in result.violations] == ["S00@2024-01-10T00:00:00+00:00"]


def test_calendar_frequency_cv_windows() -> None:
    frame = _cv_frame(2, ["2024-01-01", "2024-02-01"], horizon=2, freq="MS")
    assert _run_cv(frame, horizon=2, freq="MS").status is CheckStatus.PASS
    frame.loc[0, "ds"] = pd.Timestamp("2024-02-15")
    result = _run_cv(frame, horizon=2, freq="MS")
    assert [v.location for v in result.violations] == ["S00@2024-01-01T00:00:00"]


def test_descending_grid_never_passes() -> None:
    frame = pd.DataFrame(
        {
            "unique_id": ["A", "A"],
            "cutoff": ["2024-01-10", "2024-01-10"],
            "ds": ["2024-01-09", "2024-01-08"],
            "y": [1.0, 1.0],
        }
    )
    result = _run_cv(frame, horizon=2, freq="-1D")
    assert result.status is CheckStatus.FAIL
    assert _by_code(result, "FG-CUTOFF-004").evidence["reason"] == "misaligned"
