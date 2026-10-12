"""ForecastGuard CI — the quality gate for forecasting backtests.

Validates a Nixtla-native forecasting pipeline (``unique_id`` / ``ds`` / ``y``)
*before* its backtest is trusted, via three deliberately narrow checks:

1. **Cutoff integrity** — deterministic dataframe validation
2. **Known-future covariates** — declared availability contract validation
3. **Runtime leakage** — behavioural perturbation (the moat)

See ``docs/ForecastGuard_PRD.md`` for the product spec and
``docs/ARCHITECTURE.md`` for the module map.
"""

from forecastguard.models.ranking import CandidateImpact, RankingAudit, RankingComparison
from forecastguard.models.report import (
    CheckResult,
    CheckStatus,
    Report,
    Severity,
    Violation,
)
from forecastguard.models.spec import (
    AvailabilitySpec,
    ForecastSpec,
    MLForecastAdapterSpec,
    RevisionSpec,
)
from forecastguard.ranking import compare_rankings
from forecastguard.replay import ReplayPipeline
from forecastguard.runner import run_checks

__all__ = [
    "AvailabilitySpec",
    "CandidateImpact",
    "CheckResult",
    "CheckStatus",
    "ForecastSpec",
    "MLForecastAdapterSpec",
    "RankingAudit",
    "RankingComparison",
    "ReplayPipeline",
    "Report",
    "RevisionSpec",
    "Severity",
    "Violation",
    "compare_rankings",
    "run_checks",
]

__version__ = "0.2.0"
