"""Show a winner reversal when a toy forecast loses access to future actuals."""

import pandas as pd

from forecastguard import ForecastSpec, compare_rankings


def main() -> None:
    """Construct submitted/replayed forecasts at two origins and compare them."""
    history = pd.DataFrame(
        {
            "unique_id": ["A"] * 6,
            "ds": pd.date_range("2024-01-01", periods=6, freq="D"),
            "y": [10.0, 11.0, 12.0, 13.0, 14.0, 15.0],
        }
    )
    submitted_windows = []
    replay_windows = []
    for origin in pd.to_datetime(["2024-01-03", "2024-01-04"]):
        train = history.loc[history.ds <= origin]
        future = history.loc[history.ds > origin].head(2).copy()
        last = float(train.y.iloc[-1])
        slope = last - float(train.y.iloc[-2])
        # Candidate A improperly reads the holdout target in the submitted run.
        future["candidate_a"] = future.y
        # Candidate B uses only observations published by this origin.
        future["candidate_b"] = [last + slope * step + 0.25 for step in (1, 2)]
        future["origin"] = origin
        submitted_windows.append(future)
        # Explicit toy repair: A falls back to persistence when actuals are unavailable.
        # This policy is supplied by the caller, not inferred by ForecastGuard.
        replay_windows.append(future.assign(candidate_a=last))
    audit = compare_rankings(
        ForecastSpec(cutoff_col="origin", horizon=2, freq="D"),
        submitted=pd.concat(submitted_windows, ignore_index=True),
        replay=pd.concat(replay_windows, ignore_index=True),
        candidates=["candidate_a", "candidate_b"],
        replay_policy=(
            "Synthetic observations are available at event time. At each origin, "
            "A uses the last available target instead of future actuals; B uses a "
            "trailing trend plus 0.25. Scoring targets remain identical."
        ),
    )
    assert audit.result.status == "pass"
    assert audit.comparisons[0].submitted_winners == ["candidate_a"]
    assert audit.comparisons[0].replay_winners == ["candidate_b"]
    print(audit.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
