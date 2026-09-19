from __future__ import annotations

import pandas as pd
import pytest

from forecastguard.checks.comparison import aggregate, changed_columns, indexed_output
from forecastguard.models.report import CheckResult, CheckStatus

pytestmark = pytest.mark.unit


def test_nullable_categories_compare_missingness() -> None:
    frame = pd.DataFrame(
        {
            "id": ["A", "A"],
            "time": pd.date_range("2024-01-01", periods=2),
            "feature": pd.Series(["known", pd.NA], dtype="string"),
        }
    )
    baseline = indexed_output(frame, "id", "time")
    candidate = indexed_output(
        frame.assign(feature=pd.Series([pd.NA, pd.NA], dtype="string")), "id", "time"
    )
    assert baseline is not None and candidate is not None
    changes = changed_columns(baseline, candidate)
    assert changes["feature"]["changed_pre_cutoff_rows"] == 1


def test_comparison_cannot_silently_intersect_different_rows() -> None:
    frame = pd.DataFrame(
        {"id": ["A", "A"], "time": pd.date_range("2024-01-01", periods=2), "feature": [1.0, 2.0]}
    )
    indexed = indexed_output(frame, "id", "time")
    assert indexed is not None
    with pytest.raises(ValueError, match="aligned"):
        changed_columns(indexed, indexed.head(1))


def test_categorical_features_compare_values_not_category_dictionaries() -> None:
    frame = pd.DataFrame({"id": ["A", "A"], "time": pd.date_range("2024-01-01", periods=2)})
    left = indexed_output(frame.assign(feature=pd.Categorical(["a", "a"])), "id", "time")
    right = indexed_output(frame.assign(feature=pd.Categorical(["a", "b"])), "id", "time")
    assert left is not None and right is not None
    assert changed_columns(left, right)["feature"]["changed_pre_cutoff_rows"] == 1


def test_aggregation_preserves_errors() -> None:
    result = aggregate([CheckResult.errored("runtime_leakage", "Runtime", "failed")], "probe")
    assert result.status is CheckStatus.ERROR
    assert result.detail == "failed"
