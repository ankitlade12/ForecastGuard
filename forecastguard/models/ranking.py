"""Structured descriptive comparisons; these are not leakage verdicts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from forecastguard.models.report import CheckResult


class CandidateImpact(BaseModel):
    """MAE and competition ranks; positive deltas mean worse replay performance."""

    model_config = ConfigDict(allow_inf_nan=False)

    candidate: str
    submitted_mae: float = Field(ge=0)
    replay_mae: float = Field(ge=0)
    mae_delta: float
    submitted_rank: int = Field(ge=1)
    replay_rank: int = Field(ge=1)
    rank_delta: int


class RankingComparison(BaseModel):
    """One pooled comparison or one origin; exact ties share rank and winner status."""

    cutoff: str | None = None
    rows: int = Field(gt=0)
    scores: list[CandidateImpact]
    submitted_winners: list[str]
    replay_winners: list[str]
    winner_changed: bool


class RankingAudit(BaseModel):
    """Complete or explicitly skipped ranking analysis over caller-supplied evidence."""

    schema_version: Literal["1.0"] = "1.0"
    metric: Literal["mae"] = "mae"
    replay_policy: str
    result: CheckResult
    compared_rows: int = Field(default=0, ge=0)
    comparisons: list[RankingComparison] = Field(default_factory=list)
    scope_notes: list[str] = Field(
        default_factory=lambda: [
            "Descriptive comparison of supplied predictions, not proof of leakage or a validated replay.",
            "MAE weights each supplied series/origin/horizon row equally; overlapping targets count per origin.",
            "Coverage is relative to submitted rows; an origin/series omitted from both frames is not detectable.",
            "Replay provenance and availability policy are caller assertions; no uncertainty estimates are computed.",
        ]
    )
