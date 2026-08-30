"""Unit tests for RuntimeLeakageCheck — the behavioural-perturbation moat."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from forecastguard.checks.protocol import CheckContext
from forecastguard.checks.runtime_leak import RuntimeLeakageCheck
from forecastguard.models.report import CheckResult, CheckStatus
from forecastguard.models.spec import ForecastSpec

pytestmark = pytest.mark.unit


def _frame(extra: dict[str, Any] | None = None) -> pd.DataFrame:
    data: dict[str, Any] = {
        "unique_id": ["A"] * 6 + ["B"] * 6,
        "ds": [f"2024-01-0{i}" for i in range(1, 7)] * 2,
        "y": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
    }
    if extra:
        data.update(extra)
    return pd.DataFrame(data)


def _run(
    feature_fn: Callable[[pd.DataFrame], pd.DataFrame] | None,
    *,
    frame: pd.DataFrame | None = None,
    cutoff: str = "2024-01-04",
    horizon: int = 2,
    future_covariates: list[str] | None = None,
) -> CheckResult:
    spec = ForecastSpec(
        data=Path("unused.csv"),
        cutoff=cutoff,
        horizon=horizon,
        freq="D",
        future_covariates=future_covariates or [],
    )
    ctx = CheckContext(
        spec=spec, frame=frame if frame is not None else _frame(), feature_fn=feature_fn
    )
    return RuntimeLeakageCheck().run(ctx)


# --- feature functions --------------------------------------------------------


def _clean_lag(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["unique_id", "ds"]).copy()
    df["lag1"] = df.groupby("unique_id")["y"].shift(1)
    return df[["unique_id", "ds", "lag1"]]


def _centered_window(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["unique_id", "ds"]).copy()
    df["centered"] = df.groupby("unique_id")["y"].transform(
        lambda s: s.rolling(3, center=True, min_periods=1).mean()
    )
    return df[["unique_id", "ds", "centered"]]


def _global_mean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["unique_id", "ds"]).copy()
    df["demeaned"] = df["y"] - df.groupby("unique_id")["y"].transform("mean")
    return df[["unique_id", "ds", "demeaned"]]


# --- behaviour ----------------------------------------------------------------


def test_clean_trailing_feature_passes() -> None:
    result = _run(_clean_lag)
    assert result.status is CheckStatus.PASS
    assert result.violations == []
    assert "no future sensitivity detected" in result.summary.lower()
    assert "leak-free" not in result.summary.lower()


def test_centered_window_leak_detected() -> None:
    result = _run(_centered_window)
    assert result.status is CheckStatus.FAIL
    assert [v.code for v in result.violations] == ["FG-LEAK-001"]
    assert result.violations[0].location == "centered"


def test_global_scaler_leak_detected() -> None:
    result = _run(_global_mean)
    assert result.status is CheckStatus.FAIL
    assert result.violations[0].location == "demeaned"
    assert result.violations[0].evidence["changed_pre_cutoff_rows"]  # > 0


def test_known_future_covariate_is_not_flagged() -> None:
    # A forward-looking feature over a DECLARED future covariate is legitimate:
    # the column is preserved in the mask, so the value doesn't move.
    frame = _frame({"cal": [1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1]})

    def fwd_cal(df: pd.DataFrame) -> pd.DataFrame:
        df = df.sort_values(["unique_id", "ds"]).copy()
        df["next_cal"] = df.groupby("unique_id")["cal"].shift(-1)
        return df[["unique_id", "ds", "next_cal"]]

    result = _run(fwd_cal, frame=frame, future_covariates=["cal"])
    assert result.status is CheckStatus.PASS


def test_undeclared_forward_covariate_is_flagged() -> None:
    # Same feature, but `cal` is NOT declared future — so it's masked in the
    # future and the forward-looking feature moves: flagged.
    frame = _frame({"cal": [1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1]})

    def fwd_cal(df: pd.DataFrame) -> pd.DataFrame:
        df = df.sort_values(["unique_id", "ds"]).copy()
        df["next_cal"] = df.groupby("unique_id")["cal"].shift(-1)
        return df[["unique_id", "ds", "next_cal"]]

    result = _run(fwd_cal, frame=frame, future_covariates=[])
    assert result.status is CheckStatus.FAIL
    assert result.violations[0].location == "next_cal"


# --- loud skips (never pass silently) -----------------------------------------


def test_no_feature_fn_skips() -> None:
    result = _run(None)
    assert result.status is CheckStatus.SKIPPED
    assert "feature_fn" in (result.detail or "")


def test_nondeterministic_feature_fn_skips() -> None:
    def nondet(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["r"] = np.random.default_rng().normal(size=len(df))
        return df[["unique_id", "ds", "r"]]

    result = _run(nondet)
    assert result.status is CheckStatus.SKIPPED
    assert "nondeterministic" in (result.detail or "")


def test_feature_fn_error_skips() -> None:
    def boom(df: pd.DataFrame) -> pd.DataFrame:
        raise ValueError("kaboom")

    result = _run(boom)
    assert result.status is CheckStatus.SKIPPED
    assert "kaboom" in (result.detail or "")


def test_output_without_id_time_skips() -> None:
    def noid(df: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({"f": [1, 2, 3]})

    result = _run(noid)
    assert result.status is CheckStatus.SKIPPED


def test_output_without_comparable_pre_cutoff_rows_skips() -> None:
    def future_only(df: pd.DataFrame) -> pd.DataFrame:
        future = pd.to_datetime(df["ds"]) > pd.Timestamp("2024-01-04")
        return df.loc[future, ["unique_id", "ds"]].assign(f=1)

    result = _run(future_only)
    assert result.status is CheckStatus.SKIPPED
    assert "pre-cutoff" in (result.detail or "")


def test_output_with_unaligned_feature_columns_skips() -> None:
    def conditional_feature(df: pd.DataFrame) -> pd.DataFrame:
        df = df.sort_values(["unique_id", "ds"]).copy()
        df["lag1"] = df.groupby("unique_id")["y"].shift(1)
        if df["y"].isna().any():
            return df[["unique_id", "ds", "lag1"]]
        df["whole_series_mean"] = df.groupby("unique_id")["y"].transform("mean")
        return df[["unique_id", "ds", "lag1", "whole_series_mean"]]

    result = _run(conditional_feature)
    assert result.status is CheckStatus.SKIPPED
    assert "feature columns" in (result.detail or "")


def test_no_future_rows_skips() -> None:
    result = _run(_clean_lag, cutoff="2024-01-31")
    assert result.status is CheckStatus.SKIPPED
    assert "nothing to hide" in (result.detail or "")


def test_rolling_leakage_evidence_identifies_each_affected_window() -> None:
    spec = ForecastSpec(
        data=Path("unused.csv"),
        cutoffs=["2024-01-02", "2024-01-04"],
        horizon=2,
        freq="D",
    )
    result = RuntimeLeakageCheck().run(
        CheckContext(spec=spec, frame=_frame(), feature_fn=_global_mean)
    )
    assert result.status is CheckStatus.FAIL
    assert {violation.evidence["cutoff"] for violation in result.violations} == {
        "2024-01-02T00:00:00",
        "2024-01-04T00:00:00",
    }


def test_runtime_leakage_skips_cv_output_without_raw_history() -> None:
    frame = pd.DataFrame(
        {
            "unique_id": ["A", "A"],
            "cutoff": ["2024-01-02", "2024-01-02"],
            "ds": ["2024-01-03", "2024-01-04"],
            "y": [1, 2],
        }
    )
    spec = ForecastSpec(data=Path("unused.csv"), cutoff_col="cutoff", horizon=2, freq="D")
    result = RuntimeLeakageCheck().run(
        CheckContext(spec=spec, frame=frame, feature_fn=_global_mean)
    )
    assert result.status is CheckStatus.SKIPPED
    assert "raw history" in (result.detail or "")


def test_feature_perturbation_modes_are_reported() -> None:
    spec = ForecastSpec(
        data=Path("unused.csv"),
        cutoff="2024-01-04",
        horizon=2,
        freq="D",
        perturbations=["nullify", "noise", "sign_flip"],
        perturbation_seed=42,
    )
    result = RuntimeLeakageCheck().run(
        CheckContext(spec=spec, frame=_frame(), feature_fn=_global_mean)
    )
    assert result.status is CheckStatus.FAIL
    assert {violation.evidence["perturbation"] for violation in result.violations} == {
        "nullify",
        "noise",
        "sign_flip",
    }
