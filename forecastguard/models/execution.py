"""Typed coverage and diagnostic outputs shared by the CLI and API."""

from typing import Literal

from pydantic import BaseModel, Field

Component = Literal["feature", "forecast", "pipeline"]


class ProbeCoverage(BaseModel):
    """One requested origin/component/mode comparison, including missing work."""

    component: Component
    cutoff: str
    mode: str
    status: Literal["not_run", "pass", "fail", "skipped", "error"] = "not_run"
    compared_rows: int = 0
    detail: str | None = None


class Diagnostic(BaseModel):
    """Additional evidence that never determines the original gate verdict."""

    component: Component
    cutoff: str
    input_column: str | None = None
    mode: str | None = None
    status: Literal["sensitive", "unchanged", "skipped"]
    outputs: list[str] = Field(default_factory=list)
    detail: str
    suggestion: str | None = None
