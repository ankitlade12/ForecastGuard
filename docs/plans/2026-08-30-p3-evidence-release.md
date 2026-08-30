# P3 / Slice 5 — Evidence, explanations, CI, and release

**Date:** 2026-08-30

**Status:** Complete locally; external publication credential-blocked

**Goal:** Turn the complete detector into a measurable, explainable, and
release-ready OSS CI product.

## Deliverables

- Deterministic `nullify`, `noise`, and `sign_flip` perturbation modes with
  configured seed and fallback behavior.
- Point-in-time availability declarations using explicit availability timestamp
  columns, checked at historical event time and at every forecast origin.
- An AST hint layer that adds source locations only after a behavioural failure;
  it never creates or suppresses a verdict.
- Public mutation and scale benchmarks with machine-readable output.
- GitHub annotations, step summary, versioned JSON artifact, and SARIF export.
- Hardened composite Action and release workflow, Nixtla tutorial, README demo
  asset, changelog/architecture/decision updates, and clean package artifacts.

## Acceptance

- The mutation corpus detects every seeded leak and passes every causal control.
- Scale results determine whether a Polars backend is justified; the decision is
  recorded rather than assumed.
- JSON, SARIF, GitHub, and human renderers preserve one typed `Report` source.
- Python 3.12/3.13 CI, clean wheel installation, all examples, Action-equivalent
  execution, and package metadata checks pass.
- External GitHub/PyPI publication is attempted only after local gates pass;
  account-level blockers are reported exactly.
