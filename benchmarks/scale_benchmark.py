"""Reproducible pandas-core scale benchmark with JSON output."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from forecastguard.checks.cutoff import CutoffIntegrityCheck
from forecastguard.checks.protocol import CheckContext
from forecastguard.models.spec import ForecastSpec


def run_scale(series: int, periods: int, horizon: int) -> dict[str, object]:
    dates = pd.date_range("2024-01-01", periods=periods, freq="D")
    frame = pd.DataFrame(
        {
            "unique_id": np.repeat(np.arange(series).astype(str), periods),
            "ds": np.tile(dates.to_numpy(), series),
            "y": np.arange(series * periods, dtype=float),
        }
    )
    cutoff = dates[-horizon - 1]
    spec = ForecastSpec(
        data=Path("unused.csv"),
        cutoff=cutoff.isoformat(),
        horizon=horizon,
        freq="D",
    )
    started = time.perf_counter()
    result = CutoffIntegrityCheck().run(CheckContext(spec=spec, frame=frame))
    elapsed = time.perf_counter() - started
    rows = len(frame)
    rate = rows / elapsed
    return {
        "schema_version": "1.0",
        "backend": "pandas",
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
    args = parser.parse_args()
    if args.series <= 0 or args.periods <= args.horizon or args.horizon <= 0:
        parser.error("require series > 0 and periods > horizon > 0")
    print(json.dumps(run_scale(args.series, args.periods, args.horizon), indent=2))


if __name__ == "__main__":
    main()
