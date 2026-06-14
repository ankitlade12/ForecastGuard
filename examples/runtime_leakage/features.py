"""Feature functions for the ForecastGuard runtime-leakage demo.

`clean_features` is leak-free (trailing only). `leaky_features` contains two
classic leaks. Point a spec's `feature_fn` at one of these (e.g.
``feature_fn: "features:leaky_features"``) and run ForecastGuard.
"""

from __future__ import annotations

import pandas as pd


def clean_features(df: pd.DataFrame) -> pd.DataFrame:
    """Trailing-only features — each pre-cutoff value depends only on the past."""
    df = df.sort_values(["unique_id", "ds"]).copy()
    by = df.groupby("unique_id")["y"]
    df["lag_1"] = by.shift(1)
    df["roll_mean_3"] = by.transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    return df[["unique_id", "ds", "lag_1", "roll_mean_3"]]


def leaky_features(df: pd.DataFrame) -> pd.DataFrame:
    """Two leaks hiding next to one honest feature.

    * ``lag_1`` — fine (trailing).
    * ``centered_mean_3`` — a centered window reads one step into the future.
    * ``y_vs_series_mean`` — subtracts a mean fit over the whole series (incl. future).
    """
    df = df.sort_values(["unique_id", "ds"]).copy()
    by = df.groupby("unique_id")["y"]
    df["lag_1"] = by.shift(1)
    df["centered_mean_3"] = by.transform(
        lambda s: s.rolling(3, center=True, min_periods=1).mean()
    )
    df["y_vs_series_mean"] = df["y"] - by.transform("mean")
    return df[["unique_id", "ds", "lag_1", "centered_mean_3", "y_vs_series_mean"]]
