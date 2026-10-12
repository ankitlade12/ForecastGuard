"""Ranking impact requires comparable evidence, not just plausible scores."""

import sys

import pandas as pd
import pytest

import forecastguard.ranking as ranking
from forecastguard import ForecastSpec, RankingAudit, compare_rankings

pytestmark = pytest.mark.unit


def evidence() -> tuple[ForecastSpec, pd.DataFrame, pd.DataFrame]:
    spec = ForecastSpec(cutoff_col="origin", horizon=2, freq="D")
    submitted = pd.DataFrame(
        {
            "unique_id": ["A"] * 4,
            "origin": ["2024-01-01"] * 2 + ["2024-01-02"] * 2,
            "ds": ["2024-01-02", "2024-01-03", "2024-01-03", "2024-01-04"],
            "y": [10.0] * 4,
            "a": [10.0] * 4,
            "b": [12.0] * 4,
        }
    )
    replay = submitted.assign(a=15.0)
    return spec, submitted, replay


def test_reversal_alignment_and_serialization() -> None:
    spec, submitted, replay = evidence()
    before = submitted.copy(deep=True)
    report = compare_rankings(
        spec,
        submitted=submitted,
        replay=replay.iloc[::-1],
        candidates=["a", "b"],
        replay_policy="archived inputs at origin",
    )
    assert report.result.status == "pass"
    assert report.compared_rows == 4
    assert len(report.comparisons) == 3
    overall = report.comparisons[0]
    assert overall.winner_changed
    assert overall.submitted_winners == ["a"]
    assert overall.replay_winners == ["b"]
    assert overall.scores[0].mae_delta == 5.0
    assert overall.scores[0].rank_delta == 1
    assert RankingAudit.model_validate_json(report.model_dump_json()) == report
    pd.testing.assert_frame_equal(submitted, before)


def test_unchanged_and_tied_winners() -> None:
    spec, submitted, _ = evidence()
    for frame, winners in [(submitted, ["a"]), (submitted.assign(b=10.0), ["a", "b"])]:
        report = compare_rankings(
            spec,
            submitted=frame,
            replay=frame,
            candidates=["a", "b"],
            replay_policy="same archived inputs",
        )
        assert report.result.status == "pass"
        assert not report.comparisons[0].winner_changed
        assert report.comparisons[0].replay_winners == winners


@pytest.mark.parametrize(
    "problem",
    [
        "missing_row",
        "extra_row",
        "duplicate",
        "nan",
        "inf",
        "string",
        "bool",
        "complex",
        "target",
        "missing_column",
        "empty",
        "date",
        "null_id",
        "duplicate_column",
        "overflow",
        "nullable_na",
    ],
)
def test_unusable_evidence_skips_without_partial_rankings(problem: str) -> None:
    spec, submitted, replay = evidence()
    if problem == "missing_row":
        replay = replay.iloc[1:]
    elif problem == "extra_row":
        replay = pd.concat([replay, replay.assign(unique_id="B")])
    elif problem == "duplicate":
        replay = pd.concat([replay, replay.iloc[:1]])
    elif problem in {"nan", "inf", "overflow"}:
        replay["a"] = {"nan": float("nan"), "inf": float("inf"), "overflow": 1e308}[problem]
        if problem == "overflow":
            submitted["y"] = replay["y"] = -1e308
    elif problem in {"string", "bool", "complex"}:
        replay["a"] = {"string": "5", "bool": True, "complex": 1 + 2j}[problem]
    elif problem == "target":
        replay["y"] = 9.0
    elif problem == "missing_column":
        replay = replay.drop(columns="b")
    elif problem == "empty":
        replay = replay.iloc[:0]
    elif problem == "date":
        replay["ds"] = "bad"
    elif problem == "null_id":
        replay["unique_id"] = None
    elif problem == "duplicate_column":
        replay = pd.concat([replay, replay[["a"]]], axis=1)
    elif problem == "nullable_na":
        replay["a"] = pd.array([10, None, 10, 10], dtype="Int64")
    report = compare_rankings(
        spec,
        submitted=submitted,
        replay=replay,
        candidates=["a", "b"],
        replay_policy="archived inputs",
    )
    assert report.result.status == "skipped"
    assert report.result.detail
    assert not report.comparisons
    assert report.compared_rows == 0


def test_custom_columns_and_datetime_alignment() -> None:
    _, submitted, replay = evidence()
    names = {"unique_id": "store", "ds": "date", "y": "actual", "origin": "cut"}
    spec = ForecastSpec(
        id_col="store", time_col="date", target_col="actual", cutoff_col="cut", horizon=2, freq="D"
    )
    replay["ds"] = pd.to_datetime(replay["ds"])
    replay["origin"] = pd.to_datetime(replay["origin"])
    report = compare_rankings(
        spec,
        submitted=submitted.rename(columns=names),
        replay=replay.rename(columns=names),
        candidates=["a", "b"],
        replay_policy="archived inputs",
    )
    assert report.result.status == "pass"


@pytest.mark.parametrize(
    "candidates,policy",
    [(["a"], "archive"), (["a", "a"], "archive"), (["a", "y"], "archive"), (["a", "b"], " ")],
)
def test_invalid_declarations(candidates: list[str], policy: str) -> None:
    spec, submitted, replay = evidence()
    report = compare_rankings(
        spec, submitted=submitted, replay=replay, candidates=candidates, replay_policy=policy
    )
    assert report.result.status == "skipped"


def test_requires_explicit_cv_origins() -> None:
    _, submitted, replay = evidence()
    spec = ForecastSpec(cutoff="2024-01-01", horizon=2, freq="D")
    report = compare_rankings(
        spec, submitted=submitted, replay=replay, candidates=["a", "b"], replay_policy="archive"
    )
    assert report.result.status == "skipped"


def test_origin_rankings_can_differ_from_pooled_ranking() -> None:
    spec, submitted, replay = evidence()
    replay["a"] = [10.0, 10.0, 15.0, 15.0]
    report = compare_rankings(
        spec, submitted=submitted, replay=replay, candidates=["a", "b"], replay_policy="archive"
    )
    overall, first, second = report.comparisons
    assert overall.scores[0].replay_mae == 2.5
    assert overall.replay_winners == ["b"]
    assert not first.winner_changed
    assert second.winner_changed


@pytest.mark.parametrize("problem", ["whole_origin", "wrong_grid", "wrong_series"])
def test_full_windows_cannot_hide_coverage_mismatches(problem: str) -> None:
    spec, submitted, replay = evidence()
    if problem == "whole_origin":
        replay = replay.iloc[:2]
    elif problem == "wrong_grid":
        replay.loc[0, "ds"] = "2024-01-01"
    else:
        replay["unique_id"] = "B"
    report = compare_rankings(
        spec, submitted=submitted, replay=replay, candidates=["a", "b"], replay_policy="archive"
    )
    assert report.result.status == "skipped"
    assert not report.comparisons


def test_skip_preserves_structured_cutoff_violations() -> None:
    spec, submitted, replay = evidence()
    report = compare_rankings(
        spec,
        submitted=submitted,
        replay=replay.iloc[1:],
        candidates=["a", "b"],
        replay_policy="archive",
    )
    assert report.result.status == "skipped"
    assert (report.result.detail or "").startswith("replay:")
    [violation] = report.result.violations
    assert violation.code == "FG-CUTOFF-004"
    assert violation.location == "A@2024-01-01T00:00:00"


def test_unexpected_internal_errors_are_not_reported_as_skips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(*args: object, **kwargs: object) -> None:
        raise TypeError("internal bug")

    monkeypatch.setattr(ranking, "_compare", broken)
    spec, submitted, replay = evidence()
    with pytest.raises(TypeError, match="internal bug"):
        compare_rankings(
            spec, submitted=submitted, replay=replay, candidates=["a", "b"], replay_policy="p"
        )


def test_large_integer_predictions_do_not_silently_become_a_tie() -> None:
    spec, submitted, _ = evidence()
    submitted["y"] = 2**53
    submitted["a"] = 2**53 + 1
    submitted["b"] = 2**53
    report = compare_rankings(
        spec, submitted=submitted, replay=submitted, candidates=["a", "b"], replay_policy="archive"
    )
    assert report.result.status == "skipped"
    assert "integer" in (report.result.detail or "")


def test_finite_errors_overflowing_summation_skip() -> None:
    spec = ForecastSpec(cutoff_col="origin", horizon=1, freq="D")
    frame = pd.DataFrame(
        {
            "unique_id": list("ABC"),
            "origin": ["2024-01-01"] * 3,
            "ds": ["2024-01-02"] * 3,
            "y": [0.0] * 3,
            "a": [sys.float_info.max] * 3,
            "b": [1.0] * 3,
        }
    )
    report = compare_rankings(
        spec, submitted=frame, replay=frame, candidates=["a", "b"], replay_policy="archive"
    )
    assert report.result.status == "skipped"
    assert "overflow" in (report.result.detail or "")


def test_row_order_does_not_change_near_tied_rankings() -> None:
    spec = ForecastSpec(cutoff_col="origin", horizon=1, freq="D")
    frame = pd.DataFrame(
        {
            "unique_id": list("ABCD"),
            "origin": ["2024-01-01"] * 4,
            "ds": ["2024-01-02"] * 4,
            "y": [0.0] * 4,
            "a": [1e16, 1.0, 1.0, 1.0],
            "b": [1.0, 1.0, 1.0, 1e16],
        }
    )
    reports = [
        compare_rankings(
            spec, submitted=ordered, replay=frame, candidates=["a", "b"], replay_policy="archive"
        )
        for ordered in (frame, frame.iloc[::-1])
    ]
    assert reports[0] == reports[1]
    assert reports[0].comparisons[0].submitted_winners == ["a", "b"]


def test_competition_ranks_and_pooling_across_series() -> None:
    spec, submitted, _ = evidence()
    frame = pd.concat([submitted.assign(c=14.0), submitted.assign(unique_id="B", c=14.0)])
    frame["b"] = frame["a"]
    report = compare_rankings(
        spec, submitted=frame, replay=frame, candidates=["a", "b", "c"], replay_policy="archive"
    )
    assert report.compared_rows == 8
    assert [score.submitted_rank for score in report.comparisons[0].scores] == [1, 1, 3]
    assert [comparison.rows for comparison in report.comparisons] == [8, 4, 4]
