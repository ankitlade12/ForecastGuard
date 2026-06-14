# Examples

## quickstart

A minimal Nixtla frame + spec so you can run the gate immediately:

```bash
forecastguard run --spec examples/quickstart/forecastguard.yaml
```

Cutoff integrity and known-future covariates **run and pass** on this clean spec;
runtime leakage **skips loudly** because `feature_fn` is intentionally omitted.
Exit code is `0`; add `--strict` to make the loud skip fail.

## cutoff_integrity/ — clean → broken

Demonstrates the deterministic cutoff check: a clean spec that passes, and a
corrupted one that fails with `FG-CUTOFF-001/003/004`. See its
[README](cutoff_integrity/README.md).

## known_future/ — clean → broken

Demonstrates the declared-vs-used contract diff: a clean spec, and one whose
`future_covariates` declaration is inconsistent with the data
(`FG-FUTURE-001/002`). See its [README](known_future/README.md).

## runtime_leakage/ — leaky → clean (the moat)

The headline demo: a real `feature_fn` that reads across the cutoff (`leaky.yaml`)
vs. one that doesn't (`clean.yaml`), over the same data. The leaky run fails with
`FG-LEAK-001`; the clean run passes all three checks. See its
[README](runtime_leakage/README.md).
