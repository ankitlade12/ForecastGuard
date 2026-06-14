"""The forecasting-pipeline contract ForecastGuard validates.

A :class:`ForecastSpec` is the declared, machine-checkable description of a
user's backtest: which frame to read, the Nixtla column contract, where the
train/validation cutoff sits, the forecast horizon, which covariates are
*declared* known-at-predict-time, and (optionally) the feature-engineering
function used for the runtime-leakage check.

The spec is normally loaded from ``forecastguard.yaml`` — see
:func:`forecastguard.config.load_spec`.
"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class ForecastSpec(BaseModel):
    """Declared contract for one forecasting backtest.

    Attributes:
        name: Optional human label for the spec, surfaced in the report.
        data: Path to the dataset (``.csv`` or ``.parquet``) in long Nixtla
            format — one row per (series, timestamp).
        id_col: Series identifier column. Nixtla default ``unique_id``.
        time_col: Timestamp column. Nixtla default ``ds``.
        target_col: Target column. Nixtla default ``y``.
        cutoff: ISO-8601 train/validation boundary. Training rows satisfy
            ``ds <= cutoff``; validation rows fall strictly after it.
        horizon: Forecast horizon in periods. Must be positive.
        freq: pandas offset alias describing the series spacing (e.g. ``"D"``,
            ``"MS"``, ``"W-MON"``).
        future_covariates: Columns the user *declares* will be known at predict
            time in production (calendar features, planned promotions, ...).
            The known-future check diffs this against what the pipeline
            actually consumes.
        static_covariates: Per-series, time-invariant columns.
        feature_fn: Dotted reference (``"package.module:callable"``) to the
            feature-engineering function. Required for the runtime-leakage
            check; when absent that check *skips loudly* rather than passing
            silently.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    data: Path
    id_col: str = "unique_id"
    time_col: str = "ds"
    target_col: str = "y"
    cutoff: str = Field(min_length=1)
    horizon: int = Field(gt=0)
    freq: str = Field(min_length=1)
    future_covariates: list[str] = Field(default_factory=list)
    static_covariates: list[str] = Field(default_factory=list)
    feature_fn: str | None = None
