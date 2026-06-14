---
name: Bug report
about: A check fired when it shouldn't (false positive) or missed something it should catch
title: "[bug] "
labels: bug
---

**What happened**
A clear description of the bug.

**Which check**
`cutoff_integrity` / `known_future_covariates` / `runtime_leakage` / CLI / runner.

**Minimal repro**
The smallest `forecastguard.yaml` + a tiny frame (or snippet) that reproduces it.

```yaml
# forecastguard.yaml
```

```
# command + output / exit code
forecastguard run --spec forecastguard.yaml
```

**Expected vs actual**
What the verdict should have been, and what it was.

**Environment**
- forecastguard version:
- Python version:
- OS:
