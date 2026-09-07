"""AST hints explain behavioural findings without creating verdicts."""

from __future__ import annotations

import pandas as pd
import pytest

from forecastguard.explain import source_hints

pytestmark = pytest.mark.unit


def _risky_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["lead"] = out.groupby("unique_id")["y"].shift(-1)
    out["centered"] = out.groupby("unique_id")["y"].transform(
        lambda values: values.rolling(3, center=True).mean()
    )
    return out


def test_ast_hints_have_source_lines_for_known_constructs() -> None:
    hints = source_hints(_risky_features, "tests.unit.test_explain:_risky_features", "feature")
    assert {hint.rule for hint in hints} == {"forward-shift", "centered-window"}
    assert all(hint.line > 0 for hint in hints)


def test_ast_hints_are_empty_when_source_has_no_known_pattern() -> None:
    def clean(frame: pd.DataFrame) -> pd.DataFrame:
        return frame.copy()

    assert source_hints(clean, "clean", "feature") == []
