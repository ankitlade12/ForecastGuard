"""Run clean and intentionally leaky feature checks entirely in memory."""

import json

import pandas as pd

import forecastguard
from forecastguard.render import sarif_json


def features(frame: pd.DataFrame) -> pd.DataFrame:
    """Build a causal lag inside the tested boundary."""
    return frame[["unique_id", "ds"]].assign(lag=frame.groupby("unique_id")["y"].shift(1))


def leaky_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Intentionally read tomorrow's target."""
    return frame[["unique_id", "ds"]].assign(lead=frame.groupby("unique_id")["y"].shift(-1))


def main() -> None:
    """Exercise the installed public API and both report formats without files."""
    frame = pd.DataFrame(
        {
            "unique_id": ["A"] * 6,
            "ds": pd.date_range("2024-01-01", periods=6, freq="D"),
            "y": [1.0, 3.0, 2.0, 4.0, 6.0, 5.0],
        }
    )
    spec = forecastguard.ForecastSpec(
        cutoff="2024-01-04",
        horizon=2,
        freq="D",
        perturbations=["nullify", "noise", "sign_flip"],
    )
    clean = forecastguard.run_checks(spec, frame=frame, feature_fn=features)
    leaky = forecastguard.run_checks(spec, frame=frame, feature_fn=leaky_features)
    assert clean.exit_code(strict=True) == 0
    assert leaky.exit_code(strict=True) == 1
    assert {v.code for r in leaky.results for v in r.violations} == {"FG-LEAK-001"}
    assert forecastguard.Report.model_validate_json(leaky.model_dump_json()) == leaky
    assert leaky.coverage and all(probe.status == "fail" for probe in leaky.coverage)
    assert json.loads(sarif_json(leaky))["runs"][0]["results"]
    print("Clean pipeline: PASS; intentional leak: FG-LEAK-001; JSON/SARIF: valid")


if __name__ == "__main__":
    main()
