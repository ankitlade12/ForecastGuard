# Runtime-leakage example (leaky → clean) — the moat

The headline demo. Same data, same cutoff; only the feature function differs.
[`features.py`](features.py) defines both; run from this directory (or the repo
root) so `features` imports.

## clean — passes

```bash
forecastguard run --spec examples/runtime_leakage/clean.yaml
```

`clean_features` uses only trailing features (`lag_1`, a trailing rolling mean).
Hiding the future doesn't change any pre-cutoff value, so the check **passes**.

## leaky — fails

```bash
forecastguard run --spec examples/runtime_leakage/leaky.yaml
```

`leaky_features` hides two leaks next to one honest feature:

| Feature | Leak | Caught |
|---|---|---|
| `lag_1` | none (trailing) | — (stays clean) |
| `centered_mean_3` | centered window reads one step into the future | `FG-LEAK-001` |
| `y_vs_series_mean` | subtracts a mean fit over the whole series, future included | `FG-LEAK-001` |

ForecastGuard re-runs the feature function with the future masked and diffs the
pre-cutoff values — the two leaking features move, `lag_1` doesn't. Exit `1`.

## How it works (and what it won't do)

The mask preserves declared `future_covariates` and `static_covariates` (genuinely
known at predict time) and NaNs out the future target + past-only covariates. So a
forward-looking feature over a *declared* future covariate is **not** flagged. If
`feature_fn` is nondeterministic, raises, or returns an output that can't be
aligned, the check **skips loudly** rather than guessing. See
[docs/DECISIONS.md](../../docs/DECISIONS.md) (D-013).
