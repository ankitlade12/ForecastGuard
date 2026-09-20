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
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

PerturbationMode = Literal["nullify", "noise", "sign_flip"]


def _default_perturbations() -> list[PerturbationMode]:
    return ["nullify"]


class MLForecastAdapterSpec(BaseModel):
    """How the runner obtains a fitted MLForecast object for introspection."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["mlforecast"] = "mlforecast"
    model_path: Path | None = None
    model_fn: str | None = None

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        if int(self.model_path is not None) + int(self.model_fn is not None) != 1:
            raise ValueError("MLForecast adapter requires exactly one of model_path or model_fn")
        return self


class AvailabilitySpec(BaseModel):
    """Point-in-time availability timestamp for one future covariate."""

    model_config = ConfigDict(extra="forbid")

    covariate: str = Field(min_length=1)
    available_at_col: str = Field(min_length=1)


class RevisionSpec(BaseModel):
    """Sidecar versions used to enforce latest-available values at each origin."""

    model_config = ConfigDict(extra="forbid")
    column: str = Field(min_length=1)
    data: Path
    value_col: str = Field(default="value", min_length=1)
    available_at_col: str = Field(default="available_at", min_length=1)
    policy: Literal["latest_available"] = "latest_available"


class ForecastSpec(BaseModel):
    """Declared contract for one forecasting backtest.

    Attributes:
        name: Optional human label for the spec, surfaced in the report.
        data: Path to the dataset (``.csv`` or ``.parquet``) in long Nixtla
            format — one row per (series, timestamp). May be omitted when
            passing ``frame`` directly to ``run_checks``.
        id_col: Series identifier column. Nixtla default ``unique_id``.
        time_col: Timestamp column. Nixtla default ``ds``.
        target_col: Target column. Nixtla default ``y``.
        cutoff: Legacy single ISO-8601 train/validation boundary.
        cutoffs: Rolling-origin boundaries for a raw history panel. Each
            validation window is bounded to ``horizon`` periods, so later
            history can remain in the same frame.
        cutoff_col: Column containing the origin for each row of an already
            materialized cross-validation result (for example MLForecast's
            ``cutoff`` output column).
        horizon: Forecast horizon in periods. Must be positive.
        freq: pandas offset alias describing the series spacing (e.g. ``"D"``,
            ``"MS"``, ``"W-MON"``).
        future_covariates: Columns the user *declares* will be known at predict
            time in production (calendar features, planned promotions, ...).
            The known-future check validates that availability declaration
            against the holdout data. Model-consumption inspection requires a
            future framework adapter.
        static_covariates: Per-series, time-invariant columns.
        feature_fn: Dotted reference (``"package.module:callable"``) to the
            feature-engineering function. Required for the runtime-leakage
            check; when absent that check *skips loudly* rather than passing
            silently.
        adapter: Optional fitted-MLForecast introspection configuration.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    data: Path | None = None
    id_col: str = Field(default="unique_id", min_length=1)
    time_col: str = Field(default="ds", min_length=1)
    target_col: str = Field(default="y", min_length=1)
    cutoff: str | None = Field(default=None, min_length=1)
    cutoffs: list[str] = Field(default_factory=list)
    cutoff_col: str | None = Field(default=None, min_length=1)
    horizon: int = Field(gt=0)
    freq: str = Field(min_length=1)
    future_covariates: list[str] = Field(default_factory=list)
    static_covariates: list[str] = Field(default_factory=list)
    availability: list[AvailabilitySpec] = Field(default_factory=list)
    feature_fn: str | None = None
    forecast_fn: str | None = None
    perturbations: list[PerturbationMode] = Field(default_factory=_default_perturbations)
    perturbation_seed: int = 0
    max_probe_calls: int | None = Field(default=None, ge=0)
    adapter: MLForecastAdapterSpec | None = None
    pipeline_factory: str | None = Field(default=None, min_length=1)
    diagnostics: bool = False
    max_diagnostic_calls: int = Field(default=20, ge=0)
    revisions: list[RevisionSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_column_roles(self) -> Self:
        """Reject ambiguous or duplicated column-role declarations."""
        if self.pipeline_factory and (self.feature_fn or self.forecast_fn):
            raise ValueError("pipeline_factory is mutually exclusive with feature_fn/forecast_fn")
        revision_columns = [revision.column for revision in self.revisions]
        if len(set(revision_columns)) != len(revision_columns):
            raise ValueError("declare at most one revision history per column")
        for revision in self.revisions:
            if revision.column in {
                self.id_col,
                self.time_col,
                self.cutoff_col,
                *self.static_covariates,
            }:
                raise ValueError("revision column cannot be identity, time, cutoff, or static")
            if (
                len({self.id_col, self.time_col, revision.value_col, revision.available_at_col})
                != 4
            ):
                raise ValueError(
                    "revision value/availability columns must be distinct from id/time"
                )
        sources = (
            int(self.cutoff is not None)
            + int(bool(self.cutoffs))
            + int(self.cutoff_col is not None)
        )
        if sources != 1:
            raise ValueError("declare exactly one of cutoff, cutoffs, or cutoff_col")
        if any(not cutoff for cutoff in self.cutoffs):
            raise ValueError("cutoffs must not contain empty values")
        if len(set(self.cutoffs)) != len(self.cutoffs):
            raise ValueError("cutoffs must not contain duplicate values")
        if not self.perturbations:
            raise ValueError("perturbations must contain at least one mode")
        if len(set(self.perturbations)) != len(self.perturbations):
            raise ValueError("perturbations must not contain duplicate modes")

        core = [self.id_col, self.time_col, self.target_col]
        if len(set(core)) != len(core):
            raise ValueError("id_col, time_col, and target_col must name distinct columns")

        for role, columns in (
            ("future_covariates", self.future_covariates),
            ("static_covariates", self.static_covariates),
        ):
            if any(not column for column in columns):
                raise ValueError(f"{role} must not contain empty column names")
            if len(set(columns)) != len(columns):
                raise ValueError(f"{role} must not contain duplicate column names")
            overlap = sorted(set(columns) & set(core))
            if overlap:
                raise ValueError(f"{role} overlaps reserved columns: {', '.join(overlap)}")

        if self.cutoff_col is not None:
            cutoff_overlap = {self.cutoff_col} & {
                *core,
                *self.future_covariates,
                *self.static_covariates,
            }
            if cutoff_overlap:
                raise ValueError(
                    "cutoff_col overlaps another column role: " + ", ".join(sorted(cutoff_overlap))
                )

        overlap = sorted(set(self.future_covariates) & set(self.static_covariates))
        if overlap:
            raise ValueError(
                "future_covariates and static_covariates overlap: " + ", ".join(overlap)
            )

        availability_covariates = [item.covariate for item in self.availability]
        availability_columns = [item.available_at_col for item in self.availability]
        if len(set(availability_covariates)) != len(availability_covariates):
            raise ValueError("availability must not declare a covariate more than once")
        undeclared = sorted(set(availability_covariates) - set(self.future_covariates))
        if undeclared:
            raise ValueError(
                "availability covariates must be declared future_covariates: "
                + ", ".join(undeclared)
            )
        reserved = {
            *core,
            *self.future_covariates,
            *self.static_covariates,
        }
        if self.cutoff_col is not None:
            reserved.add(self.cutoff_col)
        column_overlap = sorted(set(availability_columns) & reserved)
        if column_overlap:
            raise ValueError(
                "availability timestamp columns overlap another role: " + ", ".join(column_overlap)
            )
        return self
