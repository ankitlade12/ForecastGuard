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
