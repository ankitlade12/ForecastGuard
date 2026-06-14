"""Shared fixtures for the test suite."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from forecastguard.checks import CheckContext
from forecastguard.models.spec import ForecastSpec

REPO_ROOT = Path(__file__).resolve().parents[1]
QUICKSTART_SPEC = REPO_ROOT / "examples" / "quickstart" / "forecastguard.yaml"


@pytest.fixture
def sample_frame() -> pd.DataFrame:
    """A tiny two-series Nixtla frame with one covariate."""
    return pd.DataFrame(
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
            "y": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "promo": [0, 1, 0, 1, 0, 1],
        }
    )


@pytest.fixture
def sample_spec(tmp_path: Path) -> ForecastSpec:
    """A valid spec (data path need not exist for context-free unit tests)."""
    return ForecastSpec(
        name="test",
        data=tmp_path / "data.csv",
        cutoff="2024-01-02",
        horizon=1,
        freq="D",
        future_covariates=["promo"],
    )


@pytest.fixture
def check_context(sample_spec: ForecastSpec, sample_frame: pd.DataFrame) -> CheckContext:
    """A ready-to-run context with no feature function."""
    return CheckContext(spec=sample_spec, frame=sample_frame, feature_fn=None)
