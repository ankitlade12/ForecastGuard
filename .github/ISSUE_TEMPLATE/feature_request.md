---
name: Feature request
about: Suggest a new check or enhancement
title: "[feat] "
labels: enhancement
---

**The pipeline error you want caught**
What inflates a backtest today that ForecastGuard doesn't catch?

**Proposed check / behavior**
How would it detect that? Deterministic dataframe rule, declared-vs-used diff,
behavioural perturbation, or something new?

**Honest scope**
Could it false-positive on a correctly-built pipeline? How do we keep the
zero-false-positive bar (see DECISIONS D-002)?

**Alternatives considered**
Anything you've tried or ruled out.
