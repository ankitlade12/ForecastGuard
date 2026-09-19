"""Deterministic, contract-aware future-input perturbations."""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype

from forecastguard.models.spec import ForecastSpec

PerturbationMode = Literal["nullify", "noise", "sign_flip"]


def perturb_unknowns(
    frame: pd.DataFrame,
    spec: ForecastSpec,
    rows: pd.Series,
    mode: PerturbationMode,
    *,
    seed: int,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """Perturb target and past-only dynamic covariates on selected rows.

    Declared future and static covariates, identity/time metadata, and a CV
    cutoff column are preserved. Non-numeric columns fall back to nullification
    for modes that require arithmetic.
    """
    keep = {spec.id_col, spec.time_col, *spec.future_covariates, *spec.static_covariates}
    if spec.cutoff_col is not None:
        keep.add(spec.cutoff_col)
    columns = [
        column
        for column in frame.columns
        if column not in keep and (columns is None or column in columns)
    ]
    perturbed = frame.copy()
    rng = np.random.default_rng(seed)
    for column in columns:
        if mode == "nullify" or not is_numeric_dtype(perturbed[column]):
            perturbed[column] = perturbed[column].mask(rows)
            continue
        perturbed[column] = perturbed[column].astype(float)
        values = perturbed.loc[rows, column]
        if mode == "sign_flip":
            perturbed.loc[rows, column] = -values
            continue
        scale = float(values.std(skipna=True))
        if not np.isfinite(scale) or scale == 0:
            scale = max(float(values.abs().mean(skipna=True)), 1.0)
        noise = rng.normal(loc=0.0, scale=scale, size=int(rows.sum()))
        perturbed.loc[rows, column] = values.to_numpy(dtype=float) + noise
    return perturbed
