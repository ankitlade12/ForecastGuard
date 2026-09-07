# Security Policy

ForecastGuard is a local-first developer tool: it reads your dataset and, for the
runtime-leakage check, imports and calls the feature function you point it at. It
makes no network calls and runs entirely in your environment.

## Executable configuration

Runtime checks execute `feature_fn` and `forecast_fn`; adapter inspection may
execute `model_fn` or load serialized models through `model_path`. Only use code
and model files you trust. User callables run in-process with your permissions;
ForecastGuard is not a sandbox. User code may perform its own IO or network calls.
The call budget limits probe count, not the duration or side effects of a call.

## Reporting a vulnerability

Please report suspected vulnerabilities privately rather than opening a public
issue. Use GitHub's **"Report a vulnerability"** (Security advisories) on the
repository, or email the maintainer. We aim to acknowledge reports within a few
days and will coordinate a fix and disclosure timeline with you.

## Supported versions

During the `0.x` series, only the latest release receives fixes.
