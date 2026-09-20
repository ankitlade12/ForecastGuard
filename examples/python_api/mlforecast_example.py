"""Validate real MLForecast predictions in memory; install the nixtla extra."""

import pandas as pd
from mlforecast import MLForecast
from sklearn.linear_model import LinearRegression

import forecastguard


def forecast(train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
    """Fit afresh using history only; consume declared future promotions."""
    model = MLForecast(models=LinearRegression(), freq="D", lags=[1, 2])
    model.fit(train[["unique_id", "ds", "y", "promo"]], static_features=[])
    horizon = int(future.groupby("unique_id").size().iloc[0])
    return model.predict(horizon, X_df=future[["unique_id", "ds", "promo"]])


def leaky_forecast(train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
    """Intentionally return actual future targets as predictions."""
    return future[["unique_id", "ds"]].assign(prediction=future["y"])


def main() -> None:
    """Verify a rolling forecast and an intentional future-target dependency."""
    frame = pd.DataFrame(
        {
            "unique_id": ["A"] * 30,
            "ds": pd.date_range("2024-01-01", periods=30, freq="D"),
            "y": [float(10 + i % 7 + i / 10) for i in range(30)],
            "promo": [float(i % 2) for i in range(30)],
        }
    )
    spec = forecastguard.ForecastSpec(
        cutoffs=["2024-01-26", "2024-01-28"],
        horizon=2,
        freq="D",
        future_covariates=["promo"],
        perturbations=["nullify", "noise", "sign_flip"],
    )
    clean = forecastguard.run_checks(spec, frame=frame, forecast_fn=forecast)
    leaky = forecastguard.run_checks(spec, frame=frame, forecast_fn=leaky_forecast)
    assert clean.exit_code(strict=True) == 0
    assert leaky.exit_code(strict=True) == 1
    assert clean.runtime_calls == 10
    assert {v.code for r in leaky.results for v in r.violations} == {"FG-FORECAST-001"}
    print("MLForecast: PASS across two origins; intentional leak: FG-FORECAST-001")


if __name__ == "__main__":
    main()
