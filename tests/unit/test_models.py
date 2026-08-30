"""Unit tests for the typed contract: ForecastSpec, Report, CheckResult."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from forecastguard.models.report import (
    CheckResult,
    CheckStatus,
    Report,
    Severity,
    Violation,
)
from forecastguard.models.spec import ForecastSpec, MLForecastAdapterSpec

pytestmark = pytest.mark.unit


def test_forecastspec_nixtla_defaults(tmp_path: Path) -> None:
    spec = ForecastSpec(data=tmp_path / "d.csv", cutoff="2024-01-01", horizon=7, freq="D")
    assert (spec.id_col, spec.time_col, spec.target_col) == ("unique_id", "ds", "y")
    assert spec.feature_fn is None


def test_forecastspec_accepts_rolling_cutoffs(tmp_path: Path) -> None:
    spec = ForecastSpec(
        data=tmp_path / "d.csv",
        cutoffs=["2024-01-01", "2024-01-08"],
        horizon=7,
        freq="D",
    )
    assert spec.cutoff is None
    assert spec.cutoffs == ["2024-01-01", "2024-01-08"]


def test_forecastspec_accepts_cv_cutoff_column(tmp_path: Path) -> None:
    spec = ForecastSpec(data=tmp_path / "cv.csv", cutoff_col="cutoff", horizon=7, freq="D")
    assert spec.cutoff_col == "cutoff"


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"cutoff": "2024-01-01", "cutoffs": ["2024-01-08"]},
        {"cutoff": "2024-01-01", "cutoff_col": "cutoff"},
        {"cutoffs": ["2024-01-01", "2024-01-01"]},
    ],
)
def test_forecastspec_requires_one_unambiguous_window_source(
    tmp_path: Path, kwargs: dict[str, object]
) -> None:
    with pytest.raises(ValidationError):
        ForecastSpec(data=tmp_path / "d.csv", horizon=1, freq="D", **kwargs)


def test_forecastspec_rejects_nonpositive_horizon(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        ForecastSpec(data=tmp_path / "d.csv", cutoff="2024-01-01", horizon=0, freq="D")


def test_forecastspec_forbids_unknown_keys(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        ForecastSpec(
            data=tmp_path / "d.csv",
            cutoff="2024-01-01",
            horizon=1,
            freq="D",
            bogus="nope",  # type: ignore[call-arg]
        )


def test_mlforecast_adapter_requires_exactly_one_model_source() -> None:
    with pytest.raises(ValidationError):
        MLForecastAdapterSpec()
    with pytest.raises(ValidationError):
        MLForecastAdapterSpec(model_path=Path("model"), model_fn="module:factory")


def test_forecastspec_rejects_duplicate_or_empty_perturbations(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        ForecastSpec(
            data=tmp_path / "d.csv",
            cutoff="2024-01-01",
            horizon=1,
            freq="D",
            perturbations=[],
        )
    with pytest.raises(ValidationError):
        ForecastSpec(
            data=tmp_path / "d.csv",
            cutoff="2024-01-01",
            horizon=1,
            freq="D",
            perturbations=["noise", "noise"],
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"id_col": "ds"},
        {"future_covariates": ["y"]},
        {"static_covariates": ["region"], "future_covariates": ["region"]},
        {"future_covariates": ["promo", "promo"]},
        {"future_covariates": [""]},
    ],
)
def test_forecastspec_rejects_conflicting_column_roles(
    tmp_path: Path, kwargs: dict[str, object]
) -> None:
    with pytest.raises(ValidationError):
        ForecastSpec(
            data=tmp_path / "d.csv",
            cutoff="2024-01-01",
            horizon=1,
            freq="D",
            **kwargs,
        )


def test_checkresult_constructors_set_status() -> None:
    assert CheckResult.passed("c", "C", "ok").status is CheckStatus.PASS
    assert CheckResult.skipped("c", "C", "why").status is CheckStatus.SKIPPED
    assert CheckResult.errored("c", "C", "trace").status is CheckStatus.ERROR

    violation = Violation(code="FG-X-001", severity=Severity.HIGH, message="bad")
    failed = CheckResult.failed("c", "C", "nope", [violation])
    assert failed.status is CheckStatus.FAIL
    assert failed.violations[0].code == "FG-X-001"


def test_report_all_pass_exits_zero() -> None:
    report = Report(results=[CheckResult.passed("a", "A", "ok")])
    assert not report.failed
    assert report.exit_code() == 0


def test_report_fail_exits_one() -> None:
    violation = Violation(code="FG-X-001", severity=Severity.CRITICAL, message="leak")
    report = Report(results=[CheckResult.failed("a", "A", "bad", [violation])])
    assert report.failed
    assert report.exit_code() == 1


def test_report_skip_is_not_failure_unless_strict() -> None:
    report = Report(results=[CheckResult.skipped("a", "A", "no feature_fn")])
    assert not report.failed
    assert report.has_skips
    assert report.exit_code() == 0
    assert report.exit_code(strict=True) == 1


def test_report_error_counts_as_failure() -> None:
    report = Report(results=[CheckResult.errored("a", "A", "boom")])
    assert report.failed
    assert report.exit_code() == 1


def test_report_json_roundtrip() -> None:
    report = Report(spec_name="s", results=[CheckResult.passed("a", "A", "ok")])
    assert Report.model_validate_json(report.model_dump_json()) == report
    assert report.schema_version == "1.0"
