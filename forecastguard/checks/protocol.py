"""Check protocol and per-run data, callable, and window context."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from forecastguard.models.adapter import AdapterUsage
from forecastguard.models.execution import Component, Diagnostic, ProbeCoverage
from forecastguard.models.hint import SourceHint
from forecastguard.models.report import CheckResult
from forecastguard.models.spec import ForecastSpec
from forecastguard.windows import PreparedWindows, prepare_windows

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
        forecast_fn: Resolved ``(train_df, future_df) -> predictions`` callable.
        adapter_usage: Introspected framework feature usage, when available.
        adapter_error: Loud adapter precondition/error from the IO boundary.
        source_hints: Best-effort explanations; checks may attach them only to
            an independently established behavioural failure.
    """

    spec: ForecastSpec
    frame: pd.DataFrame
    feature_fn: Callable[..., pd.DataFrame] | None = None
    forecast_fn: Callable[..., pd.DataFrame] | None = None
    adapter_usage: AdapterUsage | None = None
    adapter_error: str | None = None
    source_hints: list[SourceHint] = field(default_factory=list)
    revision_frames: dict[str, pd.DataFrame] = field(default_factory=dict)
    revision_error: str | None = None
    coverage: list[ProbeCoverage] = field(default_factory=list)
    runtime_calls: int = 0
    diagnostic_calls: int = 0
    diagnostics: list[Diagnostic] = field(default_factory=list)
    pipeline_factory: Callable[[], object] | None = None

    @property
    def uses_pipeline(self) -> bool:
        """Whether the configured boundary rebuilds a pipeline for every execution."""
        return self.pipeline_factory is not None or self.spec.pipeline_factory is not None

    @cached_property
    def windows(self) -> PreparedWindows:
        return prepare_windows(self.spec, self.frame)

    @cached_property
    def coverage_by_window(self) -> dict[tuple[Component, str], list[ProbeCoverage]]:
        grouped: dict[tuple[Component, str], list[ProbeCoverage]] = {}
        for entry in self.coverage:
            grouped.setdefault((entry.component, entry.cutoff), []).append(entry)
        return grouped


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
