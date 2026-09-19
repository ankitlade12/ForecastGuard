"""Small clean/leaky pipelines for setup, replay, diagnostics and revision demos."""

import pandas as pd

from forecastguard.models.spec import ForecastSpec


class DemandPipeline:
    """Reconstruct a mean-based forecast using only allowed training history."""

    def __init__(self, *, leak: bool = False) -> None:
        self.leak = leak

    def predict(
        self, frame: pd.DataFrame, cutoff: pd.Timestamp, spec: ForecastSpec
    ) -> pd.DataFrame:
        """Fit the preprocessing statistic inside this execution, then predict."""
        ds = pd.to_datetime(frame[spec.time_col])
        training = frame if self.leak else frame.loc[ds.le(cutoff)]
        means = training.groupby(spec.id_col)[spec.target_col].mean()
        future = frame.loc[ds.gt(cutoff)]
        return future[[spec.id_col, spec.time_col]].assign(
            prediction=future[spec.id_col].map(means)
        )


def clean_factory() -> DemandPipeline:
    """Create a new pipeline for every primary or diagnostic probe."""
    return DemandPipeline()


def leaky_factory() -> DemandPipeline:
    """Create a pipeline that incorrectly fits its mean on future targets."""
    return DemandPipeline(leak=True)


def weather_forecast(train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
    """Deliberately use unavailable actual weather so diagnostics can identify it."""
    return future[["unique_id", "ds"]].assign(prediction=future["weather"])
