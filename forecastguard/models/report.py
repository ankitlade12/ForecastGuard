"""Structured outputs for a ForecastGuard run.

Every check returns a :class:`CheckResult`; a run aggregates them into a
:class:`Report`. Nothing returns free text — the CLI and (later) the hosted CI
tier render these typed payloads.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Severity(StrEnum):
    """Severity of a single violation."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class CheckStatus(StrEnum):
    """Terminal status of a check.

    ``SKIPPED`` is a *loud* skip — a precondition was missing (for example, the
    runtime check had no ``feature_fn``). It is neither pass nor fail; the
    ``--strict`` flag promotes it to a failure.
    """

    PASS = "pass"
    FAIL = "fail"
    SKIPPED = "skipped"
    ERROR = "error"


class Violation(BaseModel):
    """A single problem found by a check.

    ``code`` is a stable machine identifier (e.g. ``"FG-CUTOFF-001"``) so
    violations can be referenced and, later, selectively suppressed.
    """

    code: str = Field(min_length=1)
    severity: Severity
    message: str = Field(min_length=1)
    location: str | None = None
    evidence: dict[str, object] = Field(default_factory=dict)


class CheckResult(BaseModel):
    """Outcome of one check."""

    check_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    status: CheckStatus
    summary: str = Field(min_length=1)
    violations: list[Violation] = Field(default_factory=list)
    detail: str | None = None

    @classmethod
    def passed(cls, check_id: str, name: str, summary: str) -> CheckResult:
        """Build a passing result."""
        return cls(check_id=check_id, name=name, status=CheckStatus.PASS, summary=summary)

    @classmethod
    def failed(
        cls, check_id: str, name: str, summary: str, violations: list[Violation]
    ) -> CheckResult:
        """Build a failing result carrying one or more violations."""
        return cls(
            check_id=check_id,
            name=name,
            status=CheckStatus.FAIL,
            summary=summary,
            violations=violations,
        )

    @classmethod
    def skipped(cls, check_id: str, name: str, reason: str) -> CheckResult:
        """Build a *loud* skip — neither pass nor fail; ``reason`` is required."""
        return cls(
            check_id=check_id,
            name=name,
            status=CheckStatus.SKIPPED,
            summary="skipped",
            detail=reason,
        )

    @classmethod
    def errored(cls, check_id: str, name: str, detail: str) -> CheckResult:
        """Build a result for a check that raised unexpectedly."""
        return cls(
            check_id=check_id,
            name=name,
            status=CheckStatus.ERROR,
            summary="check raised an error",
            detail=detail,
        )


class Report(BaseModel):
    """Aggregated result of a ForecastGuard run."""

    spec_name: str | None = None
    results: list[CheckResult] = Field(default_factory=list)

    @property
    def failed(self) -> bool:
        """True if any check failed or errored."""
        return any(r.status in (CheckStatus.FAIL, CheckStatus.ERROR) for r in self.results)

    @property
    def has_skips(self) -> bool:
        """True if any check skipped loudly."""
        return any(r.status is CheckStatus.SKIPPED for r in self.results)

    def exit_code(self, *, strict: bool = False) -> int:
        """Process exit code: non-zero blocks the backtest from being trusted.

        ``FAIL``/``ERROR`` always return ``1``. A loud ``SKIPPED`` returns ``1``
        only under ``strict``; otherwise the run still exits ``0`` but the skip
        is rendered prominently.
        """
        if self.failed:
            return 1
        if strict and self.has_skips:
            return 1
        return 0
