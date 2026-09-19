"""Serial end-to-end model/CLI-boundary cost measurements and M4 smoke benchmark.

Download data separately; this runner never accesses the network. Timings exclude
download, generation, and CSV creation, but the gate includes CSV loading.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import tempfile
import time
import tracemalloc
import warnings
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
from mlforecast import MLForecast
from pydantic import BaseModel
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression

from benchmarks.feasibility_benchmark import environment, make_panel
from benchmarks.mutation_benchmark import run_mutations
from benchmarks.scale_benchmark import run_scale
from forecastguard.models.report import Report
from forecastguard.models.spec import ForecastSpec, PerturbationMode
from forecastguard.runner import run_checks

REFERENCE = "benchmarks.feasibility_performance"


class Measurement(BaseModel):
    """Individual samples and untimed Python allocation peak."""

    seconds: list[float]
    median_seconds: float
    python_peak_bytes: int


def measure_group(fns: dict[str, Callable[[], object]], repeats: int) -> dict[str, Measurement]:
    """Interleave workloads with rotating order; profile memory after all timings."""
    samples: dict[str, list[float]] = {name: [] for name in fns}
    names = list(fns)
    for repetition in range(repeats):
        offset = repetition % len(names)
        for name in names[offset:] + names[:offset]:
            start = time.perf_counter()
            fns[name]()
            samples[name].append(time.perf_counter() - start)
    measured = {}
    for name, fn in fns.items():
        tracemalloc.start()
        try:
            fn()
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        measured[name] = Measurement(
            seconds=samples[name],
            median_seconds=statistics.median(samples[name]),
            python_peak_bytes=peak,
        )
    return measured


def forecast(train: pd.DataFrame, future: pd.DataFrame, *, forest: bool = False) -> pd.DataFrame:
    """Refit a real model using allowed history and known promo inputs only."""
    train = train.assign(ds=pd.to_datetime(train["ds"]))
    future = future.assign(ds=pd.to_datetime(future["ds"]))
    first_id = train["unique_id"].iloc[0]
    frequency = pd.infer_freq(train.loc[train["unique_id"].eq(first_id), "ds"])
    if frequency is None:
        raise ValueError("benchmark requires a regular time grid")
    estimator = (
        RandomForestRegressor(n_estimators=20, max_depth=6, random_state=7, n_jobs=1)
        if forest
        else LinearRegression()
    )
    model = MLForecast(
        models={"prediction": estimator}, freq=frequency, lags=[1, 2, 7], num_threads=1
    )
    model.fit(train[["unique_id", "ds", "y", "promo"]], static_features=[])
    horizon = int(future.groupby("unique_id").size().iloc[0])
    return model.predict(horizon, X_df=future[["unique_id", "ds", "promo"]])


def forest_forecast(train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
    """Use a more expensive deterministic model for a representative cost check."""
    return forecast(train, future, forest=True)


def leaky_forecast(train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
    """Inject target leakage that halves MAE without improving genuine forecasting."""
    predictions = forecast(train, future).set_index(["unique_id", "ds"])
    actual = future.assign(ds=pd.to_datetime(future["ds"])).set_index(["unique_id", "ds"])["y"]
    predictions["prediction"] = 0.5 * predictions["prediction"] + 0.5 * actual.reindex(
        predictions.index
    )
    return predictions.reset_index()


def _mae(predictions: list[pd.DataFrame], frame: pd.DataFrame) -> float:
    absolute_errors = []
    for prediction in predictions:
        joined = prediction.merge(
            frame[["unique_id", "ds", "y"]], on=["unique_id", "ds"], validate="one_to_one"
        )
        absolute_errors.extend((joined["prediction"] - joined["y"]).abs().tolist())
    return float(np.mean(absolute_errors))


def run_timing(
    frame: pd.DataFrame,
    *,
    label: str,
    windows: int,
    horizon: int,
    modes: list[PerturbationMode],
    repeats: int,
    forest: bool = False,
) -> dict[str, object]:
    """Compare an ordinary backtest with additional guard work on the same windows."""
    dates = sorted(frame["ds"].unique())
    cutoffs = [
        pd.Timestamp(dates[-(index + 1) * horizon - 1]) for index in reversed(range(windows))
    ]
    frequency = pd.infer_freq(pd.DatetimeIndex(dates))
    if frequency is None:
        raise ValueError("regular dates required")
    fn = forest_forecast if forest else forecast
    fn_name = "forest_forecast" if forest else "forecast"
    split_frames = [
        (
            frame.loc[frame["ds"].le(cutoff)],
            frame.loc[
                frame["ds"].isin(pd.date_range(cutoff, periods=horizon + 1, freq=frequency)[1:])
            ],
        )
        for cutoff in cutoffs
    ]

    def backtest() -> list[pd.DataFrame]:
        return [fn(train, future) for train, future in split_frames]

    with tempfile.TemporaryDirectory(prefix="forecastguard-feasibility-") as directory:
        data = Path(directory) / "data.csv"
        frame.to_csv(data, index=False)
        spec = ForecastSpec(
            data=data,
            cutoffs=[value.isoformat() for value in cutoffs],
            horizon=horizon,
            freq=frequency,
            future_covariates=["promo"],
            perturbations=modes,
            forecast_fn=f"{REFERENCE}:{fn_name}",
            max_probe_calls=windows * (2 + len(modes)),
        )
        clean_predictions = backtest()  # warm JIT/model imports before measurement
        clean = run_checks(spec)
        structural_spec = spec.model_copy(update={"forecast_fn": None})
        structural_report = run_checks(structural_spec)
        measurements = measure_group(
            {
                "baseline": backtest,
                "gate": lambda: run_checks(spec),
                "structural": lambda: run_checks(structural_spec),
            },
            repeats,
        )
        baseline = measurements["baseline"]
        gate = measurements["gate"]
        structural = measurements["structural"]
        leaky: Report | None = None
        leaky_mae: float | None = None
        if not forest:
            leaky = run_checks(
                spec.model_copy(update={"forecast_fn": f"{REFERENCE}:leaky_forecast"})
            )
            leaky_mae = _mae(
                [leaky_forecast(train, future) for train, future in split_frames], frame
            )
    return {
        "label": label,
        "rows": len(frame),
        "series": int(frame["unique_id"].nunique()),
        "windows": windows,
        "horizon": horizon,
        "frequency": frequency,
        "modes": modes,
        "model": "RandomForestRegressor(20 trees, depth 6, single thread)"
        if forest
        else "LinearRegression",
        "baseline_planned_calls": windows,
        "gate_planned_calls": windows * (2 + len(modes)),
        "baseline": baseline.model_dump(),
        "additional_gate": gate.model_dump(),
        "structural_only": structural.model_dump(),
        "gate_to_baseline_ratio": gate.median_seconds / baseline.median_seconds,
        "total_backtest_plus_gate_ratio": 1 + gate.median_seconds / baseline.median_seconds,
        "clean_mae": _mae(clean_predictions, frame),
        "injected_leak_mae": leaky_mae,
        "clean_report": clean.model_dump(mode="json"),
        "injected_leak_report": leaky.model_dump(mode="json") if leaky else None,
        "structural_only_report": structural_report.model_dump(mode="json"),
    }


def load_m4(path: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    """Select a fixed first-ten-series prefix and map integer hours to timestamps."""
    raw = pd.read_csv(path)
    selected_ids = sorted(raw["unique_id"].unique())[:10]
    frame = raw.loc[raw["unique_id"].isin(selected_ids) & raw["ds"].between(1, 240)].copy()
    counts = frame.groupby("unique_id").size()
    if len(counts) != 10 or not counts.eq(240).all():
        raise ValueError("expected ten complete 240-observation M4 prefixes")
    frame["ds"] = pd.Timestamp("2024-01-01") + pd.to_timedelta(frame["ds"] - 1, unit="h")
    frame["promo"] = 0.0
    frame = frame.sort_values(["unique_id", "ds"]).reset_index(drop=True)
    return frame, {
        "source": "https://datasets-nixtla.s3.amazonaws.com/m4-hourly.csv",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "selected_ids": selected_ids,
        "observations_per_series": 240,
        "transforms": "First 240 integer hours mapped to synthetic hourly timestamps; promo=0; original targets unchanged.",
    }


def main() -> None:
    """Run the declared serial timing matrix and save raw samples and reports."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m4-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.repeats < 3:
        parser.error("at least three repetitions required")
    warnings.filterwarnings("ignore", message="The copy keyword is deprecated.*")
    timings = []
    for series, periods, windows, forest in [
        (20, 120, 2, False),
        (100, 365, 2, False),
        (100, 365, 5, False),
        (20, 120, 2, True),
    ]:
        frame = make_panel("seasonal", 7, series, periods).drop(columns="weather")
        for modes in (["nullify"], ["nullify", "noise", "sign_flip"]):
            label = f"synthetic_{series}x{periods}_{windows}windows_{'forest' if forest else 'linear'}_{len(modes)}modes"
            print(f"Measuring {label}", flush=True)
            typed_modes: list[PerturbationMode] = (
                ["nullify"] if len(modes) == 1 else ["nullify", "noise", "sign_flip"]
            )
            timings.append(
                run_timing(
                    frame,
                    label=label,
                    windows=windows,
                    horizon=7,
                    modes=typed_modes,
                    repeats=args.repeats,
                    forest=forest,
                )
            )
    m4, source = load_m4(args.m4_csv)
    print("Measuring real M4 hourly subset", flush=True)
    timings.append(
        run_timing(
            m4,
            label="M4_hourly_10x240",
            windows=2,
            horizon=24,
            modes=["nullify", "noise", "sign_flip"],
            repeats=args.repeats,
        )
    )
    scale = []
    for series in (100, 1_000, 3_000):
        print(f"Measuring cutoff-only scale: {series} series", flush=True)
        run_scale(series, 365, 28)
        runs = [run_scale(series, 365, 28) for _ in range(args.repeats)]
        scale.append({"series": series, "periods": 365, "runs": runs})
    result = {
        "schema_version": "1.0",
        "environment": environment(),
        "m4": source,
        "method": "Serial warmed-up wall-clock samples; baseline/gate/structural interleaved with rotating order within each scenario; gate includes CSV IO. Memory measured after all timed samples, Python allocations not RSS. No parallel benchmark jobs.",
        "timings": timings,
        "cutoff_only_scale": scale,
        "original_mutation_corpus": run_mutations(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Saved {args.output}", flush=True)


if __name__ == "__main__":
    main()
