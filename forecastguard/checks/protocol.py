"""The Check protocol and shared run context.

Every check depends on :class:`CheckContext` (the loaded frame + spec +
resolved feature function), never on file IO directly — the same
protocol-and-stub discipline GoldMind applies to its connectors and parsers.
New checks implement :class:`Check` and register in
:func:`forecastguard.checks.default_checks`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from forecastguard.models.report import CheckResult
from forecastguard.models.spec import ForecastSpec

if TYPE_CHECKING:
    from collections.abc import Callable

    import pandas as pd


@dataclass
class CheckContext:
    """Everything a check needs to run, resolved once per run by the runner.

    Attributes:
        spec: The validated forecasting contract.
        frame: The loaded dataset (long Nixtla format).
        feature_fn: The resolved feature-engineering callable, or ``None`` when
            the spec declared no ``feature_fn``.
    """

    spec: ForecastSpec
    frame: pd.DataFrame
    feature_fn: Callable[..., pd.DataFrame] | None = None


@runtime_checkable
class Check(Protocol):
    """Contract every check satisfies.

    ``check_id`` is a stable machine identifier; ``name`` is human-facing.
    ``run`` must be deterministic and side-effect free, and must *not* raise for
    expected problems — it returns a :class:`CheckResult` instead. The runner
    converts any unexpected exception into an ``ERROR`` result so one bad check
    never aborts the whole run.
    """

    check_id: str
    name: str

    def run(self, ctx: CheckContext) -> CheckResult: ...
