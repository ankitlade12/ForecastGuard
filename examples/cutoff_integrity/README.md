# Cutoff-integrity example (clean → broken)

Two specs over the same shape, at `cutoff: 2024-01-05`, `horizon: 2`, daily.

## clean — passes

```bash
forecastguard run --spec examples/cutoff_integrity/clean/forecastguard.yaml
```

Both series have train rows through Jan 05 and a holdout of exactly Jan 06–07
(= horizon 2). The cutoff check **passes**; the other two checks skip (stubs),
so the run exits `0`.

## broken — fails

```bash
forecastguard run --spec examples/cutoff_integrity/broken/forecastguard.yaml
```

The same data, deliberately corrupted three ways — the cutoff check **fails**
(exit `1`):

| Series | Problem | Violation |
|---|---|---|
| `A` | duplicate `(A, 2024-01-03)` row | `FG-CUTOFF-001` |
| `B` | holdout is only Jan 06 — one point, not 2 | `FG-CUTOFF-004` (`too_few`) |
| `C` | no rows after the cutoff at all | `FG-CUTOFF-003` |

Each violation carries structured evidence (the duplicated key, the expected vs.
actual holdout window, etc.). See [docs/DECISIONS.md](../../docs/DECISIONS.md)
(D-011) for the full semantics.
