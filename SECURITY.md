# Security Policy

ForecastGuard is a local-first developer tool: it reads your dataset and, for the
runtime-leakage check, imports and calls the feature function you point it at. It
makes no network calls and runs entirely in your environment.

## Note on `feature_fn`

The runtime-leakage check executes the `feature_fn` declared in your spec. Only
point ForecastGuard at code you trust — treat a `forecastguard.yaml` like any
other executable config.

## Reporting a vulnerability

Please report suspected vulnerabilities privately rather than opening a public
issue. Use GitHub's **"Report a vulnerability"** (Security advisories) on the
repository, or email the maintainer. We aim to acknowledge reports within a few
days and will coordinate a fix and disclosure timeline with you.

## Supported versions

During the `0.x` series, only the latest release receives fixes.
