"""Historical revision contracts compare exactly the information available at origin."""

from pathlib import Path

import pandas as pd
import pytest

from forecastguard.checks.known_future import KnownFutureCovariatesCheck
from forecastguard.checks.protocol import CheckContext
from forecastguard.models.spec import ForecastSpec, RevisionSpec

pytestmark = pytest.mark.unit


def context(value: float = 10) -> CheckContext:
    spec = ForecastSpec(
        data=Path("unused.csv"),
        id_col="sku",
        time_col="date",
        target_col="sales",
        cutoff="2024-01-02",
        horizon=1,
        freq="D",
        revisions=[
            RevisionSpec(
                column="sales",
                data=Path("history.csv"),
                value_col="amount",
                available_at_col="published",
            )
        ],
    )
    frame = pd.DataFrame(
        {
            "sku": ["A"] * 3,
            "date": pd.date_range("2024-01-01", periods=3),
            "sales": [value, 20, 999],
        }
    )
    history = pd.DataFrame(
        {
            "sku": ["A"] * 3,
            "date": ["2024-01-01", "2024-01-01", "2024-01-02"],
            "amount": [10, 15, 20],
            "published": ["2024-01-01", "2024-01-04", "2024-01-02"],
        }
    )
    return CheckContext(spec=spec, frame=frame, revision_frames={"sales": history})


def test_original_value_passes_and_scoring_targets_are_excluded() -> None:
    assert KnownFutureCovariatesCheck().run(context()).status.value == "pass"


@pytest.mark.parametrize("original,revised", [(1_000_000_000, 1_000_001_000), (2**54, 2**54 + 1)])
def test_revision_contract_does_not_tolerate_distinct_numeric_versions(
    original: int, revised: int
) -> None:
    ctx = context()
    ctx.frame["sales"] = [revised, 20, 999]
    ctx.revision_frames["sales"]["amount"] = [original, revised, 20]
    result = KnownFutureCovariatesCheck().run(ctx)
    assert "FG-REV-003" in {v.code for v in result.violations}


def test_later_revision_fails_with_expected_value_and_origin() -> None:
    result = KnownFutureCovariatesCheck().run(context(15))
    assert result.status.value == "fail"
    violation = next(v for v in result.violations if v.code == "FG-REV-003")
    assert violation.evidence["cutoff"] == "2024-01-02T00:00:00"
    assert violation.evidence["sample"][0]["expected"] == 10  # type: ignore[index]


def test_missing_or_ambiguous_revision_history_cannot_pass() -> None:
    ctx = context()
    ctx.revision_frames = {}
    assert KnownFutureCovariatesCheck().run(ctx).status.value != "pass"
    ctx = context()
    history = ctx.revision_frames["sales"]
    ctx.revision_frames["sales"] = pd.concat([history, history.iloc[:1]], ignore_index=True)
    assert "FG-REV-001" in {v.code for v in KnownFutureCovariatesCheck().run(ctx).violations}


def test_no_version_published_by_origin_fails() -> None:
    ctx = context()
    ctx.revision_frames["sales"]["published"] = ["2024-01-05", "2024-01-06", "2024-01-05"]
    assert "FG-REV-002" in {v.code for v in KnownFutureCovariatesCheck().run(ctx).violations}


def test_categorical_revisions_compare_values() -> None:
    ctx = context()
    ctx.frame["sales"] = pd.Categorical(["old", "unchanged", "scoring"])
    ctx.revision_frames["sales"]["amount"] = pd.Categorical(["old", "new", "unchanged"])
    assert KnownFutureCovariatesCheck().run(ctx).status.value == "pass"


def test_missing_sidecar_does_not_hide_a_loaded_history_violation() -> None:
    ctx = context(15)
    ctx.frame["weather"] = [1, 2, 3]
    ctx.spec.revisions.append(RevisionSpec(column="weather", data=Path("missing.csv")))
    ctx.revision_error = "missing.csv: FileNotFoundError"
    result = KnownFutureCovariatesCheck().run(ctx)
    assert result.status.value == "fail"
    assert "FG-REV-003" in {v.code for v in result.violations}
    assert result.detail is not None and "missing.csv" in result.detail


def test_revision_of_future_covariate_is_checked_at_origin() -> None:
    ctx = context()
    ctx.frame["promo"] = [1, 1, 3]
    ctx.spec = ctx.spec.model_copy(
        update={
            "future_covariates": ["promo"],
            "revisions": [RevisionSpec(column="promo", data=Path("promo.csv"))],
        }
    )
    ctx.revision_frames = {
        "promo": pd.DataFrame(
            {
                "sku": ["A"] * 4,
                "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-03"],
                "value": [1, 1, 2, 3],
                "available_at": ["2024-01-01"] * 3 + ["2024-01-04"],
            }
        )
    }
    result = KnownFutureCovariatesCheck().run(ctx)
    assert {v.code for v in result.violations} == {"FG-REV-003"}
    ctx.frame["promo"] = [1, 1, 2]
    assert KnownFutureCovariatesCheck().run(ctx).status.value == "pass"


def test_cv_scoring_target_revisions_are_skipped_not_certified() -> None:
    ctx = context()
    ctx.frame = ctx.frame.iloc[-1:].copy()
    ctx.frame["origin"] = "2024-01-02"
    ctx.spec = ctx.spec.model_copy(update={"cutoff": None, "cutoff_col": "origin"})
    assert KnownFutureCovariatesCheck().run(ctx).status.value == "skipped"


@pytest.mark.parametrize(
    "updates",
    [
        {"pipeline_factory": "module:create", "forecast_fn": "module:predict"},
        {"revisions": [{"column": "sales", "data": "x", "value_col": "date"}]},
        {"revisions": [{"column": "sales", "data": "x"}, {"column": "sales", "data": "y"}]},
    ],
)
def test_conflicting_replay_and_revision_contracts_are_rejected(updates: dict[str, object]) -> None:
    values = context().spec.model_dump()
    values.update(updates)
    with pytest.raises(ValueError):
        ForecastSpec.model_validate(values)
