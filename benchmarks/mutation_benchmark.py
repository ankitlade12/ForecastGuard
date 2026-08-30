"""Public mutation corpus: seeded leaks must fail and causal controls must pass."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pandas as pd

from forecastguard.checks.protocol import CheckContext
from forecastguard.checks.runtime_leak import RuntimeLeakageCheck
from forecastguard.models.report import CheckStatus
from forecastguard.models.spec import ForecastSpec


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "unique_id": ["A"] * 8 + ["B"] * 8,
            "ds": [f"2024-01-{day:02d}" for day in range(1, 9)] * 2,
            "y": [float(value) for value in range(1, 9)]
            + [float(value * 10) for value in range(1, 9)],
            "actual_weather": [float(value) for value in range(16)],
            "planned_promo": [0.0, 0, 0, 0, 0, 1, 1, 1] * 2,
        }
    )


def _lag(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.sort_values(["unique_id", "ds"]).copy()
    out["lag1"] = out.groupby("unique_id")["y"].shift(1)
    return out[["unique_id", "ds", "lag1"]]


def _centered(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.sort_values(["unique_id", "ds"]).copy()
    out["centered"] = out.groupby("unique_id")["y"].transform(
        lambda values: values.rolling(3, center=True, min_periods=1).mean()
    )
    return out[["unique_id", "ds", "centered"]]


def _whole_series(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["scaled"] = out["y"] - out.groupby("unique_id")["y"].transform("mean")
    return out[["unique_id", "ds", "scaled"]]


def _recursive(train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
    last = train.groupby("unique_id")["y"].last()
    return future[["unique_id", "ds"]].assign(yhat=future["unique_id"].map(last))


def _weather(_train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
    return future[["unique_id", "ds"]].assign(yhat=future["actual_weather"])


def _teacher(_train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
    return future[["unique_id", "ds"]].assign(yhat=future["y"])


def _planned(_train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
    return future[["unique_id", "ds"]].assign(yhat=future["planned_promo"])


def run_mutations() -> dict[str, object]:
    """Run all controls and mutations, returning machine-readable evidence."""
    frame = _frame()
    cases: list[tuple[str, bool, Callable[..., pd.DataFrame], str]] = [
        ("causal_lag", False, _lag, "feature"),
        ("centered_window", True, _centered, "feature"),
        ("whole_series_scaler", True, _whole_series, "feature"),
        ("recursive_forecast", False, _recursive, "forecast"),
        ("actual_weather", True, _weather, "forecast"),
        ("teacher_forcing", True, _teacher, "forecast"),
        ("planned_promo", False, _planned, "forecast"),
    ]
    rows: list[dict[str, object]] = []
    for name, should_fail, fn, component in cases:
        spec = ForecastSpec(
            data=Path("unused.csv"),
            cutoffs=["2024-01-04", "2024-01-06"],
            horizon=2,
            freq="D",
            future_covariates=["planned_promo"],
            perturbations=["nullify", "noise", "sign_flip"],
            perturbation_seed=7,
        )
        context = CheckContext(spec=spec, frame=frame)
        if component == "feature":
            context.feature_fn = fn
        else:
            context.forecast_fn = fn
        result = RuntimeLeakageCheck().run(context)
        detected = result.status is CheckStatus.FAIL
        rows.append(
            {
                "case": name,
                "expected": "fail" if should_fail else "pass",
                "actual": result.status.value,
                "correct": detected == should_fail,
                "codes": sorted({item.code for item in result.violations}),
            }
        )
    correct = sum(bool(row["correct"]) for row in rows)
    return {
        "schema_version": "1.0",
        "cases": rows,
        "correct": correct,
        "total": len(rows),
        "all_correct": correct == len(rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    args = parser.parse_args()
    result = run_mutations()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        cases = cast("list[dict[str, object]]", result["cases"])
        for row in cases:
            print(f"{row['case']}: expected={row['expected']} actual={row['actual']}")
        print(f"correct: {result['correct']}/{result['total']}")
    raise SystemExit(0 if result["all_correct"] else 1)


if __name__ == "__main__":
    main()
