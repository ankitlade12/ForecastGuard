# Known-future-covariates example (clean → broken)

Same shape (cutoff `2024-01-05`, horizon 2, daily). Cutoff integrity passes in
both; only the **known-future** contract differs.

## clean — passes

```bash
forecastguard run --spec examples/known_future/clean/forecastguard.yaml
```

`promo` is declared known-future and is populated through the holdout (Jan 06–07),
so the check **passes**. `temp` is an undeclared covariate; it's reported as
*past-only* in the summary, not flagged (whether it actually leaks is the runtime
check's job — Slice 4).

## broken — fails

```bash
forecastguard run --spec examples/known_future/broken/forecastguard.yaml
```

The declaration is inconsistent with the data, so the check **fails** (exit `1`):

| Declared future covariate | Problem | Violation |
|---|---|---|
| `holiday` | not a column in the data | `FG-FUTURE-001` |
| `promo` | blank across the entire holdout window | `FG-FUTURE-002` |

See [docs/DECISIONS.md](../../docs/DECISIONS.md) (D-012) for why this is a
contract check rather than a behavioural one.
