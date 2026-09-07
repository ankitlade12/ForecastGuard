"""Typed adapter evidence passed from the IO boundary into checks."""

from pydantic import BaseModel, Field


class AdapterUsage(BaseModel):
    """Raw dataframe covariates a fitted forecasting framework consumes."""

    adapter: str = Field(min_length=1)
    consumed_covariates: list[str] = Field(default_factory=list)
    feature_order: list[str] = Field(default_factory=list)
