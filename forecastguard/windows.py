"""Shared, side-effect-free validation-window helpers."""

from __future__ import annotations

import pandas as pd

from forecastguard.models.spec import ForecastSpec


def forecast_grid(
    anchor: pd.Timestamp, offset: pd.offsets.BaseOffset, horizon: int
) -> list[pd.Timestamp]:
    """Return ``anchor + 1*offset`` through ``anchor + horizon*offset``."""
    out: list[pd.Timestamp] = []
    current = anchor
    for _ in range(horizon):
        current = current + offset
        out.append(pd.Timestamp(current))
    return out


def window_cutoffs(spec: ForecastSpec, frame: pd.DataFrame) -> list[pd.Timestamp]:
    """Parse and sort the cutoffs declared by ``spec`` or present in ``frame``."""
    if spec.cutoff is not None:
        return [pd.Timestamp(spec.cutoff)]
    if spec.cutoffs:
        return sorted(pd.Timestamp(value) for value in spec.cutoffs)
    if spec.cutoff_col is None:
        return []
    parsed = pd.to_datetime(frame[spec.cutoff_col], errors="raise")
    return sorted(pd.Timestamp(value) for value in parsed.unique())


def holdout_mask(
    spec: ForecastSpec,
    frame: pd.DataFrame,
    ds: pd.Series,
    cutoff: pd.Timestamp,
    expected: list[pd.Timestamp],
) -> pd.Series:
    """Select one validation window while preserving legacy single-cutoff scope."""
    if spec.cutoff_col is not None:
        row_cutoffs = pd.to_datetime(frame[spec.cutoff_col], errors="raise")
        return row_cutoffs.eq(cutoff)
    if spec.cutoffs:
        return ds.gt(cutoff) & ds.le(expected[-1])
    return ds.gt(cutoff)


def window_location(series_id: object, cutoff: pd.Timestamp, *, rolling: bool) -> str:
    """Stable location for a series, adding the origin for rolling checks."""
    if rolling:
        return f"{series_id}@{cutoff.isoformat()}"
    return str(series_id)
