"""Generate real MLForecast cross-validation output for the rolling tutorial."""

from pathlib import Path

import pandas as pd
from mlforecast import MLForecast
from sklearn.linear_model import LinearRegression

HERE = Path(__file__).parent


def build_fitted(frame: pd.DataFrame) -> MLForecast:
    """Adapter-compatible factory returning a fitted MLForecast object."""
    model = MLForecast(models=LinearRegression(), freq="D", lags=[1, 2])
    return model.fit(frame, static_features=[])


def forecast(train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
    train = train.assign(ds=pd.to_datetime(train["ds"]))
    future = future.assign(ds=pd.to_datetime(future["ds"]))
    model = build_fitted(train[["unique_id", "ds", "y", "promo"]])
    horizon = int(future.groupby("unique_id").size().iloc[0])
    return model.predict(horizon, X_df=future[["unique_id", "ds", "promo"]])


def leaky_forecast(train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
    predictions = forecast(train, future)
    actual = future.set_index(["unique_id", "ds"])["y"]
    actual.index = pd.MultiIndex.from_arrays(
        [actual.index.get_level_values(0), pd.to_datetime(actual.index.get_level_values(1))]
    )
    predictions = predictions.set_index(["unique_id", "ds"])
    predictions["LinearRegression"] = actual.reindex(predictions.index)
    return predictions.reset_index()


def main() -> None:
    frame = pd.read_csv(HERE / "data.csv")
    frame["ds"] = pd.to_datetime(frame["ds"])
    model = MLForecast(models=LinearRegression(), freq="D", lags=[1, 2])
    cv = model.cross_validation(
        frame,
        n_windows=2,
        h=2,
        step_size=2,
        static_features=[],
    )
    cv.to_csv(HERE / "cv-generated.csv", index=False)
    print(cv)


if __name__ == "__main__":
    main()
