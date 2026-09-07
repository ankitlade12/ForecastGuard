"""Measure a real MLForecast workflow on a reproducible synthetic demand panel."""

from __future__ import annotations

import json
import statistics
import tempfile
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
from examples.nixtla_rolling.mlforecast_tutorial import forecast

from forecastguard.models.spec import ForecastSpec
from forecastguard.runner import run_checks


def _measure(fn: Callable[[], object], repeats: int) -> tuple[float, int]:
    durations = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        durations.append(time.perf_counter() - start)
    tracemalloc.start()
    try:
        fn()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return statistics.median(durations), peak


def run_integration(series: int = 20, periods: int = 120, repeats: int = 5) -> dict[str, object]:
    dates = pd.date_range("2024-01-01", periods=periods)
    rng = np.random.default_rng(7)
    frame = pd.DataFrame(
        {
            "unique_id": np.repeat([f"item_{i}" for i in range(series)], periods),
            "ds": np.tile(dates, series),
            "promo": rng.integers(0, 2, series * periods).astype(float),
        }
    )
    frame["y"] = 50 + 5 * frame["promo"] + rng.normal(0, 2, len(frame))
    horizon = 7
    cutoffs = [dates[-2 * horizon - 1], dates[-horizon - 1]]

    def backtest() -> None:
        for cutoff in cutoffs:
            train = frame.loc[frame["ds"].le(cutoff)]
            future = frame.loc[
                frame["ds"].gt(cutoff) & frame["ds"].le(cutoff + pd.Timedelta(days=horizon))
            ]
            forecast(train, future)

    with tempfile.TemporaryDirectory(prefix="forecastguard-benchmark-") as directory:
        data = Path(directory) / "data.csv"
        frame.to_csv(data, index=False)
        spec = ForecastSpec(
            data=data,
            cutoffs=[value.isoformat() for value in cutoffs],
            horizon=horizon,
            freq="D",
            future_covariates=["promo"],
            forecast_fn="examples.nixtla_rolling.mlforecast_tutorial:forecast",
            max_probe_calls=6,
        )
        backtest()
        clean = run_checks(spec)
        baseline_time, baseline_peak = _measure(backtest, repeats)
        gate_time, gate_peak = _measure(lambda: run_checks(spec), repeats)
        structural_time, _ = _measure(
            lambda: run_checks(spec.model_copy(update={"forecast_fn": None})), repeats
        )
        leaky = run_checks(
            spec.model_copy(
                update={"forecast_fn": "examples.nixtla_rolling.mlforecast_tutorial:leaky_forecast"}
            )
        )
    return {
        "data": "synthetic demand; real MLForecast LinearRegression",
        "rows": len(frame),
        "series": series,
        "windows": len(cutoffs),
        "horizon": horizon,
        "repeats": repeats,
        "baseline_forecast_calls": 2,
        "planned_gate_forecast_calls": 6,
        "baseline_seconds_median": baseline_time,
        "additional_gate_seconds_median": gate_time,
        "gate_to_baseline_ratio": gate_time / baseline_time,
        "structural_only_seconds_median": structural_time,
        "baseline_python_peak_bytes": baseline_peak,
        "gate_python_peak_bytes": gate_peak,
        "memory_scope": "tracemalloc allocations, not total process RSS; separate untimed run",
        "clean_status": clean.results[-1].status.value,
        "leaky_status": leaky.results[-1].status.value,
        "leaky_codes": sorted({v.code for r in leaky.results for v in r.violations}),
    }


if __name__ == "__main__":
    print(json.dumps(run_integration(), indent=2))
