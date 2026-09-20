"""The public Python API uses the same trust gate without temporary data files."""

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from forecastguard import CheckStatus, ForecastSpec, Report, run_checks

pytestmark = pytest.mark.integration


def test_dataframe_and_local_functions_preserve_inputs(sample_frame: pd.DataFrame) -> None:
    frame = sample_frame.rename(columns={"unique_id": "series", "ds": "time", "y": "value"})
    original = frame.copy(deep=True)
    spec = ForecastSpec(
        cutoff="2024-01-02",
        horizon=1,
        freq="D",
        id_col="series",
        time_col="time",
        target_col="value",
        future_covariates=["promo"],
    )
    before = spec.model_dump_json()

    def clean(data: pd.DataFrame) -> pd.DataFrame:
        data["lag"] = data.groupby("series")["value"].shift(1)
        return data[["series", "time", "lag"]]

    def leaky(data: pd.DataFrame) -> pd.DataFrame:
        return data[["series", "time"]].assign(lead=data.groupby("series")["value"].shift(-1))

    report = run_checks(spec, frame=frame, feature_fn=clean)
    assert report.exit_code(strict=True) == 0
    assert report.runtime_calls == 3
    assert [(c.component, c.status) for c in report.coverage] == [("feature", "pass")]
    failed = run_checks(spec, frame=frame, feature_fn=leaky)
    assert failed.exit_code(strict=True) == 1
    assert {v.code for r in failed.results for v in r.violations} == {"FG-LEAK-001"}
    assert Report.model_validate_json(failed.model_dump_json()) == failed
    assert_frame_equal(frame, original)
    assert spec.model_dump_json() == before


def test_direct_forecast_diagnostics(sample_frame: pd.DataFrame) -> None:
    spec = ForecastSpec(cutoff="2024-01-02", horizon=1, freq="D", diagnostics=True)

    def forecast(train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
        return future[["unique_id", "ds"]].assign(prediction=future["y"])

    report = run_checks(spec, frame=sample_frame, forecast_fn=forecast)
    assert report.results[-1].status is CheckStatus.FAIL
    assert report.coverage[0].component == "forecast"
    assert report.coverage[0].status == "fail"
    assert any(d.input_column == "y" and d.status == "sensitive" for d in report.diagnostics)


def test_direct_pipeline_factory(sample_frame: pd.DataFrame) -> None:
    origins: list[pd.Timestamp] = []

    class Pipeline:
        def predict(
            self, frame: pd.DataFrame, cutoff: pd.Timestamp, spec: ForecastSpec
        ) -> pd.DataFrame:
            origins.append(cutoff)
            future = frame.loc[pd.to_datetime(frame[spec.time_col]) > cutoff]
            return future[[spec.id_col, spec.time_col]].assign(prediction=1.0)

    spec = ForecastSpec(cutoff="2024-01-02", horizon=1, freq="D")
    report = run_checks(spec, frame=sample_frame, pipeline_factory=Pipeline)
    assert report.exit_code(strict=True) == 0
    assert origins == [pd.Timestamp(spec.cutoff)] * 3
    assert report.coverage[0].component == "pipeline"
    assert not any("outside configured callables" in note for note in report.scope_notes)


@pytest.mark.parametrize("blocked_by", ["structure", "budget"])
def test_direct_callable_is_not_executed_when_blocked(
    sample_frame: pd.DataFrame,
    blocked_by: str,
) -> None:
    calls = 0

    def feature(data: pd.DataFrame) -> pd.DataFrame:
        nonlocal calls
        calls += 1
        return data

    spec = ForecastSpec(
        cutoff="2024-01-02",
        horizon=1,
        freq="D",
        max_probe_calls=0 if blocked_by == "budget" else None,
    )
    frame = sample_frame.drop(columns="y") if blocked_by == "structure" else sample_frame
    report = run_checks(spec, frame=frame, feature_fn=feature)
    assert report.exit_code(strict=True) == 1
    assert report.results[-1].status is CheckStatus.SKIPPED
    assert report.coverage[0].status == "skipped"
    assert report.runtime_calls == calls == 0


@pytest.mark.parametrize("reference", ["feature_fn", "pipeline_factory"])
def test_conflicting_callable_sources_are_rejected(
    sample_frame: pd.DataFrame,
    reference: str,
) -> None:
    spec = ForecastSpec.model_validate(
        {
            "cutoff": "2024-01-02",
            "horizon": 1,
            "freq": "D",
            reference: "missing:callable",
        }
    )
    with pytest.raises(ValueError, match=r"feature_fn|pipeline_factory"):
        run_checks(spec, frame=sample_frame, feature_fn=lambda data: data)


def test_missing_data_and_missing_runtime_are_explicit(sample_frame: pd.DataFrame) -> None:
    spec = ForecastSpec(cutoff="2024-01-02", horizon=1, freq="D")
    with pytest.raises(ValueError, match=r"frame.*data|data.*frame"):
        run_checks(spec)
    report = run_checks(spec, frame=sample_frame)
    assert report.has_skips
    assert report.exit_code() == 0
    assert report.exit_code(strict=True) == 1


def test_explicit_frame_overrides_path_and_can_use_imported_reference(
    sample_frame: pd.DataFrame,
    sample_spec: ForecastSpec,
) -> None:
    # sample_spec.data deliberately does not exist.
    spec = sample_spec.model_copy(update={"feature_fn": f"{__name__}:clean_features"})
    assert run_checks(spec, frame=sample_frame).exit_code(strict=True) == 0


def clean_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Importable counterpart to a directly passed local function."""
    return frame[["unique_id", "ds"]].assign(lag=frame.groupby("unique_id")["y"].shift(1))


def test_combined_boundaries_and_custom_checks(sample_frame: pd.DataFrame) -> None:
    from forecastguard.checks import default_checks

    spec = ForecastSpec(cutoff="2024-01-02", horizon=1, freq="D")

    def forecast(train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
        return future[["unique_id", "ds"]].assign(prediction=1.0)

    for checks in (None, default_checks()):
        report = run_checks(
            spec, checks, frame=sample_frame, feature_fn=clean_features, forecast_fn=forecast
        )
        assert report.exit_code(strict=True) == 0
        assert report.runtime_calls == 6
        assert {c.component for c in report.coverage} == {"feature", "forecast"}
        assert all(c.status == "pass" for c in report.coverage)


def test_direct_replay_failure_and_budget(sample_frame: pd.DataFrame) -> None:
    calls = 0

    class LeakyPipeline:
        def predict(
            self, frame: pd.DataFrame, cutoff: pd.Timestamp, spec: ForecastSpec
        ) -> pd.DataFrame:
            future = frame.loc[pd.to_datetime(frame[spec.time_col]) > cutoff]
            return future[[spec.id_col, spec.time_col]].assign(prediction=future[spec.target_col])

    def factory() -> LeakyPipeline:
        nonlocal calls
        calls += 1
        return LeakyPipeline()

    spec = ForecastSpec(cutoff="2024-01-02", horizon=1, freq="D", diagnostics=True)
    report = run_checks(spec, frame=sample_frame, pipeline_factory=factory)
    assert report.results[-1].status is CheckStatus.FAIL
    assert report.coverage[0].component == "pipeline"
    assert any(d.component == "pipeline" and d.status == "sensitive" for d in report.diagnostics)
    assert report.runtime_calls == calls
    calls = 0
    blocked = run_checks(
        spec.model_copy(update={"max_probe_calls": 0}),
        frame=sample_frame,
        pipeline_factory=factory,
    )
    assert blocked.exit_code(strict=True) == 1
    assert blocked.runtime_calls == calls == 0
    assert blocked.coverage[0].status == "skipped"


def test_invalid_direct_callable_and_replay_combinations(sample_frame: pd.DataFrame) -> None:
    spec = ForecastSpec(cutoff="2024-01-02", horizon=1, freq="D")
    with pytest.raises(TypeError, match="feature_fn must be callable"):
        run_checks(spec, frame=sample_frame, feature_fn="not callable")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="mutually exclusive"):
        run_checks(spec, frame=sample_frame, feature_fn=clean_features, pipeline_factory=object)
    referenced = spec.model_copy(update={"forecast_fn": "missing:forecast"})
    with pytest.raises(ValueError, match="mutually exclusive"):
        run_checks(referenced, frame=sample_frame, pipeline_factory=object)
    referenced = spec.model_copy(update={"pipeline_factory": "missing:factory"})
    with pytest.raises(ValueError, match="supplied both"):
        run_checks(referenced, frame=sample_frame, pipeline_factory=object)
