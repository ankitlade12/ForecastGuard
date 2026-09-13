"""Labelled CI feasibility corpus, including deliberately undetectable leaks.

Run with ``uv run python -m benchmarks.feasibility_benchmark --output result.json``.
This is a synthetic ablation of ForecastGuard, not a competitor comparison.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from forecastguard.checks import default_checks
from forecastguard.checks.protocol import CheckContext
from forecastguard.models.report import CheckResult, CheckStatus, Report
from forecastguard.models.spec import ForecastSpec, PerturbationMode

Kind = Literal["clean", "leak", "boundary", "guard"]
KEYS = ["unique_id", "ds"]


class Observation(BaseModel):
    """Ground-truth label plus unmodified structured detector outputs."""

    case: str
    kind: Kind
    panel: str = "test"
    seed: int = 0
    configuration: str = "test"
    explanation: str = ""
    results: list[CheckResult]
    elapsed_seconds: float = 0


class Score(BaseModel):
    """Separate supported detection, boundary failures, and execution coverage."""

    observations: int = 0
    leak_cases: int = 0
    leak_detections: int = 0
    leak_misses: int = 0
    leak_detection_rate: float | None = None
    clean_cases: int = 0
    clean_passes: int = 0
    clean_false_alarms: int = 0
    clean_false_alarm_rate: float | None = None
    boundary_cases: int = 0
    boundary_detections: int = 0
    boundary_misses: int = 0
    all_leak_detection_rate: float | None = None
    guard_cases: int = 0
    guard_strict_blocks: int = 0
    abstentions: int = 0
    status_counts: dict[str, int] = Field(default_factory=dict)


def score_observations(rows: Sequence[Observation]) -> Score:
    """Count abstentions as misses, never as successful detection or clean PASS."""
    score = Score(observations=len(rows))
    for row in rows:
        statuses = {result.status for result in row.results}
        detected = CheckStatus.FAIL in statuses
        clean_pass = bool(statuses) and statuses == {CheckStatus.PASS}
        abstained = bool(statuses & {CheckStatus.SKIPPED, CheckStatus.ERROR}) or not statuses
        score.abstentions += int(abstained)
        for result in row.results:
            key = f"{result.check_id}:{result.status.value}"
            score.status_counts[key] = score.status_counts.get(key, 0) + 1
        if row.kind == "leak":
            score.leak_cases += 1
            score.leak_detections += int(detected)
            score.leak_misses += int(not detected)
        elif row.kind == "clean":
            score.clean_cases += 1
            score.clean_passes += int(clean_pass)
            score.clean_false_alarms += int(detected)
        elif row.kind == "boundary":
            score.boundary_cases += 1
            score.boundary_detections += int(detected)
            score.boundary_misses += int(not detected)
        else:
            score.guard_cases += 1
            score.guard_strict_blocks += Report(results=row.results).exit_code(strict=True)
    if score.leak_cases:
        score.leak_detection_rate = score.leak_detections / score.leak_cases
    if score.clean_cases:
        score.clean_false_alarm_rate = score.clean_false_alarms / score.clean_cases
    total_leaks = score.leak_cases + score.boundary_cases
    if total_leaks:
        score.all_leak_detection_rate = (
            score.leak_detections + score.boundary_detections
        ) / total_leaks
    return score


@dataclass
class Case:
    """One pipeline variant; callables are resolved before the check boundary."""

    name: str
    kind: Kind
    explanation: str
    feature: Callable[..., pd.DataFrame] | None = None
    forecast: Callable[..., pd.DataFrame] | None = None
    declare_weather: bool = False


def make_panel(regime: str, seed: int, series: int = 4, periods: int = 90) -> pd.DataFrame:
    """Generate independent panels with positive seasonal/trending or sparse demand."""
    rng = np.random.default_rng(seed)
    t = np.tile(np.arange(periods), series)
    ids = np.repeat(np.arange(series), periods)
    promo = rng.integers(0, 2, len(t)).astype(float)
    y = 50 + 10 * ids + 8 * np.sin(2 * np.pi * t / 7) + 5 * promo
    y = y + rng.normal(0, 2, len(t))
    if regime == "trend":
        y = y + 0.5 * t
    elif regime == "intermittent":
        y = rng.poisson(8, len(t)).astype(float) * (rng.random(len(t)) < 0.2)
    elif regime != "seasonal":
        raise ValueError(f"unknown regime: {regime}")
    return pd.DataFrame(
        {
            "unique_id": [f"item_{value}" for value in ids],
            "ds": np.tile(pd.date_range("2024-01-01", periods=periods), series),
            "y": y,
            "promo": promo,
            "weather": rng.normal(20, 5, len(t)),
        }
    )


def _feature(frame: pd.DataFrame, operation: str) -> pd.DataFrame:
    out = frame.sort_values(KEYS).copy()
    grouped = out.groupby("unique_id")["y"]
    if operation in {"lag", "shuffled", "inplace"}:
        values = grouped.shift(1)
    elif operation == "trailing":
        values = grouped.transform(lambda y: y.shift(1).rolling(7, min_periods=1).mean())
    elif operation == "expanding":
        values = grouped.transform(lambda y: y.shift(1).expanding().mean())
    elif operation == "known_future":
        values = out.groupby("unique_id")["promo"].shift(-1)
    elif operation == "lead":
        values = grouped.shift(-1)
    elif operation == "centered":
        values = grouped.transform(lambda y: y.rolling(7, center=True, min_periods=1).mean())
    elif operation == "full_mean":
        values = out["y"] - grouped.transform("mean")
    elif operation == "full_scale":
        values = (out["y"] - grouped.transform("mean")) / grouped.transform("std")
    else:
        raise ValueError(operation)
    if operation == "inplace":
        frame["feature"] = values.reindex(frame.index)
        return frame[[*KEYS, "feature"]]
    out["feature"] = values
    result = out[[*KEYS, "feature"]]
    return result.iloc[::-1] if operation == "shuffled" else result


def _forecast(train: pd.DataFrame, future: pd.DataFrame, operation: str) -> pd.DataFrame:
    out = future[KEYS].copy()
    last = train.groupby("unique_id")["y"].last()
    if operation == "last":
        values = future["unique_id"].map(last)
    elif operation == "promo":
        values = future["unique_id"].map(last) + 5 * future["promo"]
    elif operation == "target":
        values = future["y"]
    elif operation == "weather":
        values = future["weather"]
    elif operation == "teacher":
        values = future.groupby("unique_id")["y"].shift(1).fillna(future["unique_id"].map(last))
    elif operation == "positive_branch":
        # A real dependency that nullification alone can miss on positive demand.
        values = (future["y"].fillna(1.0) > 0).astype(float) * 10
    else:
        raise ValueError(operation)
    out["prediction"] = values
    return out


def make_cases(frame: pd.DataFrame) -> list[Case]:
    """Construct labels before executing probes, including three boundary leaks."""
    cases: list[Case] = []
    for operation in ("lag", "trailing", "expanding", "known_future", "shuffled", "inplace"):
        cases.append(
            Case(
                operation,
                "clean",
                "Causal feature or legitimately known future promo.",
                feature=lambda data, op=operation: _feature(data, op),
            )
        )
    for operation in ("lead", "centered", "full_mean", "full_scale"):
        cases.append(
            Case(
                operation,
                "leak",
                "Feature recomputed using unavailable post-origin targets.",
                feature=lambda data, op=operation: _feature(data, op),
            )
        )
    for operation in ("last", "promo", "target", "weather", "teacher", "positive_branch"):
        cases.append(
            Case(
                operation,
                "clean" if operation in {"last", "promo"} else "leak",
                "Predictions use allowed history/promo or injected unavailable horizon values.",
                forecast=lambda train, future, op=operation: _forecast(train, future, op),
            )
        )

    # Capture future-contaminated artifacts OUTSIDE the tested function.
    frozen_features = _feature(frame, "full_scale")
    cached_predictions = frame.set_index(KEYS)["y"].copy()

    def cached_forecast(_train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
        out = future[KEYS].copy()
        keys = pd.MultiIndex.from_frame(out)
        out["prediction"] = cached_predictions.reindex(keys).to_numpy()
        return out

    calls = 0

    def nondeterministic(train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
        nonlocal calls
        calls += 1
        out = _forecast(train, future, "last")
        out["prediction"] += calls
        return out

    cases.extend(
        [
            Case(
                "frozen_preprocessing",
                "boundary",
                "Full-series scaling happened outside probe.",
                feature=lambda _data: frozen_features.copy(),
            ),
            Case(
                "cached_actuals",
                "boundary",
                "Forecast returns actuals from an external closure.",
                forecast=cached_forecast,
            ),
            Case(
                "false_availability",
                "boundary",
                "Actual weather incorrectly declared known; no timestamps.",
                forecast=lambda train, future: _forecast(train, future, "weather"),
                declare_weather=True,
            ),
            Case("missing_callable", "guard", "Runtime callable is absent."),
            Case(
                "nondeterministic",
                "guard",
                "Baseline changes on each call.",
                forecast=nondeterministic,
            ),
            Case(
                "incomplete_predictions",
                "guard",
                "One horizon prediction is missing.",
                forecast=lambda train, future: _forecast(train, future, "last").iloc[:-1],
            ),
        ]
    )
    return cases


def run_corpus(seeds: Sequence[int] = (7, 19, 41)) -> list[Observation]:
    """Compare structural-only and one-/three-mode checks on identical labelled data."""
    observations = []
    configurations: dict[str, list[PerturbationMode]] = {
        "structural_only": ["nullify"],
        "nullify": ["nullify"],
        "three_modes": ["nullify", "noise", "sign_flip"],
    }
    for regime in ("seasonal", "trend", "intermittent"):
        for seed in seeds:
            frame = make_panel(regime, seed)
            dates = sorted(frame["ds"].unique())
            for configuration, modes in configurations.items():
                for case in make_cases(frame):
                    spec = ForecastSpec(
                        data=Path("unused.csv"),
                        cutoffs=[
                            pd.Timestamp(dates[-15]).isoformat(),
                            pd.Timestamp(dates[-8]).isoformat(),
                        ],
                        horizon=7,
                        freq="D",
                        future_covariates=["promo"] + (["weather"] if case.declare_weather else []),
                        perturbations=modes,
                        perturbation_seed=seed,
                    )
                    ctx = CheckContext(
                        spec=spec,
                        frame=frame.copy(),
                        feature_fn=case.feature,
                        forecast_fn=case.forecast,
                    )
                    checks = default_checks()
                    if configuration == "structural_only":
                        checks = [check for check in checks if check.check_id != "runtime_leakage"]
                    start = time.perf_counter()
                    results = []
                    for check in checks:
                        try:
                            results.append(check.run(ctx))
                        except Exception as exc:
                            results.append(
                                CheckResult.errored(
                                    check.check_id, check.name, f"{type(exc).__name__}: {exc}"
                                )
                            )
                    observations.append(
                        Observation(
                            case=case.name,
                            kind=case.kind,
                            panel=regime,
                            seed=seed,
                            configuration=configuration,
                            explanation=case.explanation,
                            results=results,
                            elapsed_seconds=time.perf_counter() - start,
                        )
                    )
    return observations


def environment() -> dict[str, object]:
    """Capture versions and hardware so local timing results remain interpretable."""
    return {
        "utc": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("pandas", "numpy", "pydantic", "mlforecast", "scikit-learn")
        },
    }


def main() -> None:
    """Write a reproducible artifact without treating known blind spots as success."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = run_corpus()
    scores = {
        config: score_observations(
            [row for row in rows if row.configuration == config]
        ).model_dump()
        for config in ("structural_only", "nullify", "three_modes")
    }
    result = {
        "schema_version": "1.0",
        "environment": environment(),
        "method": "Direct CheckContext checks; IO/import/CLI covered separately by integration tests and timings.",
        "design": {
            "series": 4,
            "periods": 90,
            "horizon": 7,
            "origins": 2,
            "seeds": [7, 19, 41],
            "panels": ["seasonal", "trend", "intermittent"],
        },
        "scores": scores,
        "observations": [row.model_dump(mode="json") for row in rows],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(scores, indent=2))


if __name__ == "__main__":
    main()
