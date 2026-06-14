"""ForecastGuard CI — the quality gate for forecasting backtests.

Validates a Nixtla-native forecasting pipeline (``unique_id`` / ``ds`` / ``y``)
*before* its backtest is trusted, via three deliberately narrow checks:

1. **Cutoff integrity** — deterministic dataframe validation (zero false positives)
2. **Known-future covariates** — declared-vs-used contract diff
3. **Runtime leakage** — behavioural perturbation (the moat)

See ``docs/ForecastGuard_PRD.md`` for the product spec and
``docs/ARCHITECTURE.md`` for the module map.
"""

from forecastguard.models.report import (
    CheckResult,
    CheckStatus,
    Report,
    Severity,
    Violation,
)
from forecastguard.models.spec import ForecastSpec

__all__ = [
    "CheckResult",
    "CheckStatus",
    "ForecastSpec",
    "Report",
    "Severity",
    "Violation",
]

__version__ = "0.1.0"
