"""Reproducible pandas-core scale benchmark with JSON output."""

from __future__ import annotations

import argparse
import json
import time

import numpy as np
import pandas as pd

from forecastguard.checks.cutoff import CutoffIntegrityCheck
from forecastguard.checks.protocol import CheckContext
from forecastguard.models.spec import ForecastSpec


def run_scale(
    series: int, periods: int, horizon: int, *, windows: str = "single", origins: int = 1
) -> dict[str, object]:
    dates = pd.date_range("2024-01-01", periods=periods, freq="D")
    ids = np.arange(series).astype(str)
    cutoffs = dates[-horizon - origins : -horizon]
    if windows == "cv":
        origin = np.tile(np.repeat(cutoffs.to_numpy(), horizon), series)
        steps = np.tile(np.arange(1, horizon + 1), series * origins) * np.timedelta64(1, "D")
        frame = pd.DataFrame(
            {
                "unique_id": np.repeat(ids, origins * horizon),
                "cutoff": origin,
                "ds": origin + steps,
                "y": 0.0,
            }
        )
        spec = ForecastSpec(cutoff_col="cutoff", horizon=horizon, freq="D")
    else:
        frame = pd.DataFrame(
            {
                "unique_id": np.repeat(ids, periods),
                "ds": np.tile(dates.to_numpy(), series),
                "y": np.arange(series * periods, dtype=float),
            }
        )
        if windows == "rolling":
            spec = ForecastSpec(
                cutoffs=[cutoff.isoformat() for cutoff in cutoffs], horizon=horizon, freq="D"
            )
        else:
            spec = ForecastSpec(cutoff=cutoffs[-1].isoformat(), horizon=horizon, freq="D")
    started = time.perf_counter()
    result = CutoffIntegrityCheck().run(CheckContext(spec=spec, frame=frame))
    elapsed = time.perf_counter() - started
    rows = len(frame)
    rate = rows / elapsed
    return {
        "schema_version": "1.0",
        "backend": "pandas",
        "windows": windows,
        "origins": origins,
        "series": series,
        "periods": periods,
        "rows": rows,
        "elapsed_seconds": round(elapsed, 6),
        "rows_per_second": round(rate, 2),
        "status": result.status.value,
        "polars_recommended": rate < 50_000,
        "decision_threshold_rows_per_second": 50_000,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--series", type=int, default=1_000)
    parser.add_argument("--periods", type=int, default=365)
    parser.add_argument("--horizon", type=int, default=28)
    parser.add_argument("--windows", choices=["single", "rolling", "cv"], default="single")
    parser.add_argument("--origins", type=int, default=1)
    args = parser.parse_args()
    if args.series <= 0 or args.horizon <= 0 or args.origins <= 0:
        parser.error("require series, horizon and origins > 0")
    if args.periods < args.horizon + args.origins:
        parser.error("require periods >= horizon + origins")
    if args.windows == "single" and args.origins != 1:
        parser.error("single-cutoff windows use exactly one origin")
    result = run_scale(
        args.series, args.periods, args.horizon, windows=args.windows, origins=args.origins
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
