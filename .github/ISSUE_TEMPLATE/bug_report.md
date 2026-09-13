---
name: Bug report
about: A check fired when it shouldn't (false positive) or missed something it should catch
title: "[bug] "
labels: bug
---

**What happened**
A clear description of the bug.

**Which check**
`cutoff_integrity` / `known_future_covariates` / `runtime_leakage` / setup / plan /
diagnostics / replay / revision history / documentation.

**Minimal repro**
The smallest `forecastguard.yaml` + a tiny frame (or snippet) that reproduces it.
Include the callable when runtime behaviour is involved. Use synthetic or anonymized
data and redact private values from reports. Security reports belong in SECURITY.md's
private reporting channel.

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
- model library and version (if applicable):
- violation codes and incomplete coverage (from `--format json`):
