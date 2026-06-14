# Changelog

All notable changes to ForecastGuard are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to
follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Slice 4 — Runtime-leakage check (the moat).** `RuntimeLeakageCheck` is now
  implemented (behavioural perturbation): contract-aware future masking, a
  determinism probe, and a pre-cutoff diff that flags any feature that reads
  across the cutoff (`FG-LEAK-001`). Forward-looking features over *declared*
  future covariates are not flagged. Ships with the headline
  `examples/runtime_leakage` (leaky→clean) demo and 10 unit tests. Semantics:
  DECISIONS D-013. **All three checks are now implemented.**
- **Slice 3 — Known-future-covariates check.** `KnownFutureCovariatesCheck` is
  now implemented (declared-vs-used contract diff): `FG-FUTURE-001`
  (declared covariate not a column) and `FG-FUTURE-002` (declared covariate empty
  across the holdout); undeclared covariates surfaced as past-only. Ships with
  `examples/known_future` (clean→broken) and 8 unit tests. Semantics: DECISIONS
  D-012.
- **Slice 2 — Cutoff-integrity check.** `CutoffIntegrityCheck` is now
  implemented (deterministic, zero-false-positive): duplicate `(id, ds)`,
  missing training history, empty/short/misaligned holdout vs `horizon`/`freq`,
  with structured `FG-CUTOFF-*` evidence. Ships with `examples/cutoff_integrity`
  (clean→broken) and 15 unit tests. Semantics: DECISIONS D-011.
- **Slice 1 — Foundation.** Package skeleton, typed contract (`ForecastSpec`,
  `Report`, `CheckResult`, `Violation`), `Check` protocol + `CheckContext`, the
  runner, the Click CLI (`forecastguard run`), and a runnable `examples/quickstart`.
- Docs (PRD, ARCHITECTURE, DECISIONS D-001…D-013), agent instructions, OSS
  hygiene files, CI + PyPI publish workflows, and the composite GitHub Action.

### Not yet (Slice 5 — Ship)
- GitHub Action hardening + README GIF; a Nixtla `cross_validation` tutorial PR.
- A chosen license (see README → License).
- First PyPI release.

[Unreleased]: https://github.com/ankitlade12/ForecastGuard/commits/main
