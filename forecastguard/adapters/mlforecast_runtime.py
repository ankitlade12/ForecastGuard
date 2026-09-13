"""Optional executable MLForecast bridge for generated initialization wrappers."""

import importlib

import pandas as pd


def forecast_with_mlforecast(
    train: pd.DataFrame,
    future: pd.DataFrame,
    *,
    model_factory: str | None,
    freq: str,
    id_col: str,
    time_col: str,
    target_col: str,
    future_covariates: list[str],
    static_covariates: list[str],
) -> pd.DataFrame:
    """Build and fit an unfitted user model, or a minimal reference MLForecast model."""
    from mlforecast import MLForecast

    if model_factory:
        module, _, name = model_factory.partition(":")
        model = getattr(importlib.import_module(module), name)()
        if not isinstance(model, MLForecast):
            raise TypeError("model_factory must return an unfitted MLForecast instance")
    else:
        from sklearn.linear_model import LinearRegression

        model = MLForecast(models=LinearRegression(), freq=freq, lags=[1])
    train = train.assign(**{time_col: pd.to_datetime(train[time_col])})
    future = future.assign(**{time_col: pd.to_datetime(future[time_col])})
    columns = [id_col, time_col, target_col, *future_covariates, *static_covariates]
    model.fit(
        train[columns],
        id_col=id_col,
        time_col=time_col,
        target_col=target_col,
        static_features=static_covariates,
    )
    sizes = future.groupby(id_col).size()
    if sizes.empty or sizes.nunique() != 1:
        raise ValueError("future input must have an equal positive horizon for every series")
    horizon = int(sizes.iloc[0])
    return model.predict(
        horizon, X_df=future[[id_col, time_col, *future_covariates]] if future_covariates else None
    )
