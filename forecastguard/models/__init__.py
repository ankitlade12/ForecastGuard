"""Pydantic contract for ForecastGuard — the spec in, the report out.

Structured outputs everywhere: checks never return free text, they return
typed :class:`CheckResult` objects that the CLI (and later the hosted CI tier)
render. This discipline is inherited from the GoldMind project.
"""

from forecastguard.models.report import (
    CheckResult,
    CheckStatus,
    Report,
    Severity,
    Violation,
)
from forecastguard.models.spec import AvailabilitySpec, ForecastSpec, MLForecastAdapterSpec

__all__ = [
    "AvailabilitySpec",
    "CheckResult",
    "CheckStatus",
    "ForecastSpec",
    "MLForecastAdapterSpec",
    "Report",
    "Severity",
    "Violation",
]
