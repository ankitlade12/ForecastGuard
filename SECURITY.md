# Security Policy

ForecastGuard reads datasets and runs validation in your environment. Its core
validation does not require a hosted service or make network calls. Configured
user code and model libraries may perform their own IO or network calls.

## Executable configuration

Runtime checks execute `feature_fn`, `forecast_fn` or `pipeline_factory`, including
factory-created `predict` methods; adapter inspection may
execute `model_fn` or load serialized models through `model_path`. Only use code
and model files you trust. User callables run in-process with your permissions;
ForecastGuard is not a sandbox. User code may perform its own IO or network calls.
The call budget limits probe count, not the duration or side effects of a call.

Fresh pipeline replay creates new objects but does not isolate globals, files,
caches or external services. Generated wrappers execute their configured model
factory. The `plan` command reads data and revision sidecars without importing or
executing user callables, adapters or factories.

## Reports and detection limits

JSON, SARIF, terminal output and GitHub artifacts can include sample input/output
values, series identifiers, local paths and exception details. They are not
automatically redacted. Review them before sharing and restrict artifact access
when validating private datasets.

A passing runtime probe is bounded evidence for its configured inputs and
execution boundary, not a security certification or proof of no leakage.
Revision histories and availability declarations are user-supplied evidence.
See the [support matrix](SUPPORT_MATRIX.md) and
[benchmark limitations](docs/BENCHMARK_FEASIBILITY.md).

## Reporting a vulnerability

Please report suspected vulnerabilities privately rather than opening a public
issue. Use GitHub's **"Report a vulnerability"** (Security advisories) on the
repository if private reporting is enabled, or email
[ankitlade12@gmail.com](mailto:ankitlade12@gmail.com) with the subject
`ForecastGuard security report`. Include the affected revision, impact and a
minimal reproduction without secrets. We will coordinate disclosure with you;
responses are best effort.

## Supported versions

During the `0.x` series, only the latest release receives fixes.
