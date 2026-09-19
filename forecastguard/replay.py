"""Explicit fresh-instance replay; external state is not automatically isolated."""

from collections.abc import Callable
from typing import Protocol, runtime_checkable

import pandas as pd

from forecastguard.models.spec import ForecastSpec


@runtime_checkable
class ReplayPipeline(Protocol):
    """Construct preprocessing and fit models inside predict using the supplied frame."""

    def predict(
        self, frame: pd.DataFrame, cutoff: pd.Timestamp, spec: ForecastSpec
    ) -> pd.DataFrame: ...


def replay_forecast(
    factory: Callable[[], object], spec: ForecastSpec
) -> Callable[..., pd.DataFrame]:
    """Adapt a fresh pipeline to probes of raw history plus the forecast horizon."""
    previous: object = None

    def forecast(
        train: pd.DataFrame, future: pd.DataFrame, *, cutoff: pd.Timestamp
    ) -> pd.DataFrame:
        nonlocal previous
        pipeline = factory()
        if not isinstance(pipeline, ReplayPipeline):
            raise TypeError(
                "pipeline_factory must return an object with predict(frame, cutoff, spec)"
            )
        if pipeline is previous:
            raise ValueError("pipeline_factory reused its previous object; return a fresh pipeline")
        previous = pipeline
        raw = pd.concat([train, future], ignore_index=True)
        return pipeline.predict(raw.copy(deep=True), cutoff, spec.model_copy(deep=True))

    return forecast
