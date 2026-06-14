"""The check registry.

The three checks are deliberately narrow (see ``docs/ForecastGuard_PRD.md``).
``default_checks`` returns them in report order; the runner accepts any
``Sequence[Check]`` so callers can subset or extend.
"""

from forecastguard.checks.cutoff import CutoffIntegrityCheck
from forecastguard.checks.known_future import KnownFutureCovariatesCheck
from forecastguard.checks.protocol import Check, CheckContext
from forecastguard.checks.runtime_leak import RuntimeLeakageCheck


def default_checks() -> list[Check]:
    """The three checks that run by default, in report order."""
    return [
        CutoffIntegrityCheck(),
        KnownFutureCovariatesCheck(),
        RuntimeLeakageCheck(),
    ]


__all__ = [
    "Check",
    "CheckContext",
    "CutoffIntegrityCheck",
    "KnownFutureCovariatesCheck",
    "RuntimeLeakageCheck",
    "default_checks",
]
