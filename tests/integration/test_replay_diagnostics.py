"""Replay and explanations must preserve behavioural evidence and call budgets."""

from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest

from forecastguard.checks.protocol import CheckContext
from forecastguard.execution import finish_coverage, initialize_coverage, mark_probe
from forecastguard.models.execution import ProbeCoverage
from forecastguard.models.spec import ForecastSpec
from forecastguard.runner import run_checks

pytestmark = pytest.mark.integration


def test_coverage_accounting_scans_entries_once_not_once_per_probe(tmp_path: Path) -> None:
    class CountedCoverage(list[ProbeCoverage]):
        visited = 0

        def __iter__(self) -> Iterator[ProbeCoverage]:
            for entry in super().__iter__():
                self.visited += 1
                yield entry

    origins = pd.date_range("2024-01-01", periods=100)
    spec = make_spec(tmp_path).model_copy(
        update={
            "cutoffs": [value.isoformat() for value in origins],
            "feature_fn": "unused:feature",
            "forecast_fn": "unused:forecast",
            "perturbations": ["nullify", "noise", "sign_flip"],
        }
    )
    ctx = CheckContext(spec=spec, frame=pd.read_csv(spec.data))
    initialize_coverage(ctx)
    entries = CountedCoverage(ctx.coverage)
    ctx.coverage = entries
    for cutoff in origins:
        mark_probe(ctx, "forecast", cutoff, "noise", failed=True, rows=2)
        mark_probe(ctx, "feature", cutoff, "nullify", failed=False, rows=3)
        finish_coverage(ctx, "unsupported", component="forecast", cutoff=cutoff)
    finish_coverage(ctx, "not completed")
    assert entries.visited <= 2 * len(entries)
    assert sum(e.status == "fail" for e in entries) == 100
    assert sum(e.status == "pass" for e in entries) == 100
    assert sum(e.status == "skipped" for e in entries) == 400


class LeakyPipeline:
    def predict(
        self, frame: pd.DataFrame, cutoff: pd.Timestamp, spec: ForecastSpec
    ) -> pd.DataFrame:
        # Recompute a contaminated preprocessing artifact inside every fresh instance.
        means = frame.groupby(spec.id_col)[spec.target_col].mean()
        future = frame.loc[pd.to_datetime(frame[spec.time_col]).gt(cutoff)]
        return future[[spec.id_col, spec.time_col]].assign(
            prediction=future[spec.id_col].map(means)
        )


class CleanPipeline:
    def predict(
        self, frame: pd.DataFrame, cutoff: pd.Timestamp, spec: ForecastSpec
    ) -> pd.DataFrame:
        train = frame.loc[pd.to_datetime(frame[spec.time_col]).le(cutoff)]
        future = frame.loc[pd.to_datetime(frame[spec.time_col]).gt(cutoff)]
        means = train.groupby(spec.id_col)[spec.target_col].mean()
        return future[[spec.id_col, spec.time_col]].assign(
            prediction=future[spec.id_col].map(means)
        )


def clean_factory() -> CleanPipeline:
    return CleanPipeline()


def leaky_factory() -> LeakyPipeline:
    return LeakyPipeline()


SINGLETON = CleanPipeline()


def singleton_factory() -> CleanPipeline:
    return SINGLETON


def weather_forecast(train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
    return future[["sku", "date"]].assign(prediction=future["weather"])


def partial_forecast(train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
    if future["sales"].isna().any():
        raise ValueError("null inputs unsupported")
    return weather_forecast(train, future)


def leaky_features(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[["sku", "date"]].assign(lead=frame["sales"].shift(-1))


def make_spec(tmp_path: Path) -> ForecastSpec:
    data = tmp_path / "panel.csv"
    pd.DataFrame(
        {
            "sku": ["A"] * 8,
            "date": pd.date_range("2024-01-01", periods=8),
            "sales": [10.0, 20, 30, 40, 100, 200, 300, 400],
            "weather": [2.0, 5, 8, 3, 20, 30, 40, 50],
        }
    ).to_csv(data, index=False)
    return ForecastSpec(
        data=data,
        id_col="sku",
        time_col="date",
        target_col="sales",
        cutoffs=["2024-01-04", "2024-01-06"],
        horizon=2,
        freq="D",
    )


def test_replay_catches_preprocessing_leak_and_passes_clean_pipeline(tmp_path: Path) -> None:
    spec = make_spec(tmp_path)
    clean = run_checks(spec.model_copy(update={"pipeline_factory": f"{__name__}:clean_factory"}))
    assert clean.exit_code(strict=True) == 0
    assert clean.runtime_calls == 6
    assert {entry.component for entry in clean.coverage} == {"pipeline"}
    leaky = run_checks(spec.model_copy(update={"pipeline_factory": f"{__name__}:leaky_factory"}))
    assert leaky.failed
    assert {entry.status for entry in leaky.coverage} == {"fail"}


def test_reused_pipeline_instance_skips_loudly(tmp_path: Path) -> None:
    report = run_checks(
        make_spec(tmp_path).model_copy(update={"pipeline_factory": f"{__name__}:singleton_factory"})
    )
    assert report.has_skips
    assert report.exit_code(strict=True) == 1


def test_replay_uses_explicit_origins_when_business_horizons_overlap(tmp_path: Path) -> None:
    spec = make_spec(tmp_path).model_copy(
        update={
            "cutoffs": ["2024-01-06", "2024-01-07"],
            "horizon": 1,
            "freq": "B",
            "pipeline_factory": f"{__name__}:clean_factory",
        }
    )
    frame = pd.read_csv(spec.data)
    frame = frame.loc[~frame["date"].isin(["2024-01-06", "2024-01-07"])]
    frame.to_csv(spec.data, index=False)
    report = run_checks(spec)
    assert report.exit_code(strict=True) == 0, report.model_dump_json()
    assert report.runtime_calls == 6
    assert {entry.status for entry in report.coverage} == {"pass"}

    leaky = run_checks(
        spec.model_copy(
            update={"pipeline_factory": f"{__name__}:leaky_factory", "diagnostics": True}
        )
    )
    assert leaky.failed
    assert {d.cutoff for d in leaky.diagnostics if d.status == "sensitive"} == {
        "2024-01-06T00:00:00",
        "2024-01-07T00:00:00",
    }


def test_diagnostics_identify_weather_without_blaming_target(tmp_path: Path) -> None:
    spec = make_spec(tmp_path).model_copy(
        update={"forecast_fn": f"{__name__}:weather_forecast", "diagnostics": True}
    )
    report = run_checks(spec)
    assert report.failed
    assert report.diagnostic_calls > 0
    assert {d.input_column for d in report.diagnostics if d.status == "sensitive"} == {"weather"}
    assert any(d.input_column == "sales" and d.status == "unchanged" for d in report.diagnostics)


def test_exhausted_diagnostic_budget_never_erases_primary_failure(tmp_path: Path) -> None:
    spec = make_spec(tmp_path).model_copy(
        update={
            "forecast_fn": f"{__name__}:weather_forecast",
            "diagnostics": True,
            "max_probe_calls": 6,
        }
    )
    report = run_checks(spec)
    assert report.failed
    assert report.runtime_calls == 6
    assert report.diagnostic_calls == 0
    assert any(d.status == "skipped" for d in report.diagnostics)


def test_diagnostic_calls_obey_both_caps(tmp_path: Path) -> None:
    spec = make_spec(tmp_path).model_copy(
        update={
            "forecast_fn": f"{__name__}:weather_forecast",
            "diagnostics": True,
            "max_probe_calls": 9,
            "max_diagnostic_calls": 3,
        }
    )
    report = run_checks(spec)
    assert report.runtime_calls == 9
    assert report.diagnostic_calls == 3
    assert report.failed
    assert any(d.status == "skipped" for d in report.diagnostics)


def test_partial_probe_failures_keep_coverage_and_original_verdict(tmp_path: Path) -> None:
    spec = make_spec(tmp_path).model_copy(
        update={
            "forecast_fn": f"{__name__}:partial_forecast",
            "diagnostics": True,
            "perturbations": ["nullify", "noise"],
        }
    )
    report = run_checks(spec)
    assert report.failed
    assert {entry.status for entry in report.coverage if entry.mode == "nullify"} == {"skipped"}
    assert {entry.status for entry in report.coverage if entry.mode == "noise"} == {"fail"}


def test_feature_diagnostics_use_pre_cutoff_outputs(tmp_path: Path) -> None:
    spec = make_spec(tmp_path).model_copy(
        update={"feature_fn": f"{__name__}:leaky_features", "diagnostics": True}
    )
    report = run_checks(spec)
    assert report.failed
    assert {d.input_column for d in report.diagnostics if d.status == "sensitive"} == {"sales"}


def test_replay_diagnostics_reconstruct_the_pipeline(tmp_path: Path) -> None:
    spec = make_spec(tmp_path).model_copy(
        update={"pipeline_factory": f"{__name__}:leaky_factory", "diagnostics": True}
    )
    report = run_checks(spec)
    assert report.failed
    assert {d.input_column for d in report.diagnostics if d.status == "sensitive"} == {"sales"}
    assert {d.component for d in report.diagnostics} == {"pipeline"}
