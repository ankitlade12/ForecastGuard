"""Compare model selection before and after an explicitly supplied historical replay."""

from math import fsum

import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype, is_complex_dtype, is_integer_dtype, is_numeric_dtype

from forecastguard.checks.cutoff import CutoffIntegrityCheck
from forecastguard.checks.protocol import CheckContext
from forecastguard.models.ranking import CandidateImpact, RankingAudit, RankingComparison
from forecastguard.models.report import CheckResult, CheckStatus, Violation
from forecastguard.models.spec import ForecastSpec

_CHECK_ID = "ranking_comparison"
_NAME = "Model-ranking comparison"
_OVERFLOW = "MAE arithmetic overflow; rescale targets and predictions"


class _IncomparableError(Exception):
    """Supplied evidence cannot support a complete comparison; reported as a loud skip."""

    def __init__(self, reason: str, violations: list[Violation] | None = None) -> None:
        super().__init__(reason)
        self.violations = violations or []


def compare_rankings(
    spec: ForecastSpec,
    *,
    submitted: pd.DataFrame,
    replay: pd.DataFrame,
    candidates: list[str],
    replay_policy: str,
) -> RankingAudit:
    """Compare MAE on identical materialized CV rows, overall and per origin.

    Args:
        spec: CV contract with an explicit cutoff_col, horizon and frequency.
        submitted: Original predictions, scoring targets and CV key columns.
        replay: Historical-replay predictions with identical keys and scoring targets.
        candidates: At least two distinct prediction column names in both frames.
        replay_policy: Nonempty description of how replay inputs were reconstructed.

    Returns:
        Typed analysis. Unusable evidence yields SKIPPED with no partial rankings.
        PASS only means comparison completed; it does not certify replay validity.
        This function neither runs pipelines nor changes the default leakage gate.
    """
    try:
        if spec.cutoff_col is None:
            raise _IncomparableError(
                "ranking comparison requires a materialized-CV spec with cutoff_col"
            )
        if not replay_policy.strip():
            raise _IncomparableError("replay_policy must describe historical input reconstruction")
        keys = [spec.id_col, spec.cutoff_col, spec.time_col]
        if len(candidates) < 2 or len(set(candidates)) != len(candidates):
            raise _IncomparableError("declare at least two distinct candidate prediction columns")
        if any(not name.strip() or name in {*keys, spec.target_col} for name in candidates):
            raise _IncomparableError(
                "candidate columns must be nonempty and distinct from keys/target"
            )
        left = _prepare(spec, submitted, candidates, "submitted")
        right = _prepare(spec, replay, candidates, "replay")
        if len(left) != len(right) or not left.index.isin(right.index).all():
            raise _IncomparableError(
                "submitted and replay keys must match exactly; no rows are dropped"
            )
        right = right.reindex(left.index)
        if not left[spec.target_col].eq(right[spec.target_col]).all():
            raise _IncomparableError("submitted and replay scoring targets must match exactly")
        comparisons = [_compare(left, right, spec, candidates, None)]
        origins = left.index.get_level_values(spec.cutoff_col)
        for origin in sorted(origins.unique()):
            mask = origins == origin
            comparisons.append(
                _compare(left.loc[mask], right.loc[mask], spec, candidates, origin.isoformat())
            )
        return RankingAudit(
            replay_policy=replay_policy,
            result=CheckResult.passed(
                _CHECK_ID, _NAME, "Ranking comparison completed; replay validity is not certified"
            ),
            compared_rows=len(left),
            comparisons=comparisons,
        )
    except _IncomparableError as exc:
        result = CheckResult(
            check_id=_CHECK_ID,
            name=_NAME,
            status=CheckStatus.SKIPPED,
            summary="skipped",
            detail=str(exc),
            violations=exc.violations,
        )
        return RankingAudit(replay_policy=replay_policy, result=result)


def _prepare(
    spec: ForecastSpec,
    frame: pd.DataFrame,
    candidates: list[str],
    label: str,
) -> pd.DataFrame:
    if not frame.columns.is_unique:
        raise _IncomparableError(f"{label}: duplicate column labels are unsupported")
    if frame.empty:
        raise _IncomparableError(f"{label}: no evaluation rows supplied")
    required = [spec.id_col, spec.cutoff_col, spec.time_col, spec.target_col, *candidates]
    if any(column not in frame.columns for column in required):
        raise _IncomparableError(f"{label}: missing required key, target or candidate column")
    work = frame[required].copy(deep=True)
    # The cutoff check parses keys itself, so unparseable timestamps arrive as FG-CUTOFF-011.
    result = CutoffIntegrityCheck().run(CheckContext(spec=spec, frame=work))
    if result.status is not CheckStatus.PASS:
        raise _IncomparableError(f"{label}: {result.summary}", result.violations)
    assert spec.cutoff_col is not None
    for column in (spec.time_col, spec.cutoff_col):
        work[column] = pd.to_datetime(work[column], errors="raise")
    for column in [spec.target_col, *candidates]:
        values = work[column]
        if (
            not is_numeric_dtype(values.dtype)
            or is_bool_dtype(values.dtype)
            or is_complex_dtype(values.dtype)
        ):
            raise _IncomparableError(f"{label}: {column!r} must contain real numeric values")
        if is_integer_dtype(values.dtype) and (values.gt(2**53).any() or values.lt(-(2**53)).any()):
            raise _IncomparableError(
                f"{label}: {column!r} contains integers outside the exact float64 range; "
                "rescale or center values before comparison"
            )
        if not np.isfinite(values.to_numpy(dtype=float)).all():
            raise _IncomparableError(f"{label}: {column!r} contains missing or non-finite values")
    return work.set_index([spec.id_col, spec.cutoff_col, spec.time_col])


def _compare(
    submitted: pd.DataFrame,
    replay: pd.DataFrame,
    spec: ForecastSpec,
    candidates: list[str],
    cutoff: str | None,
) -> RankingComparison:
    losses: list[list[float]] = []
    for frame in (submitted, replay):
        truth = frame[spec.target_col].to_numpy(dtype=float)
        with np.errstate(over="ignore", invalid="ignore"):
            errors = np.abs(frame[candidates].to_numpy(dtype=float) - truth[:, None])
        try:
            means = [fsum(column / len(frame)) for column in errors.T]
        except OverflowError as exc:
            raise _IncomparableError(_OVERFLOW) from exc
        if not np.isfinite(means).all():
            raise _IncomparableError(_OVERFLOW)
        losses.append([float(value) for value in means])
    before, after = losses
    scores = []
    for index, candidate in enumerate(candidates):
        rank_before = 1 + sum(value < before[index] for value in before)
        rank_after = 1 + sum(value < after[index] for value in after)
        scores.append(
            CandidateImpact(
                candidate=candidate,
                submitted_mae=before[index],
                replay_mae=after[index],
                mae_delta=after[index] - before[index],
                submitted_rank=rank_before,
                replay_rank=rank_after,
                rank_delta=rank_after - rank_before,
            )
        )
    winners_before = sorted(score.candidate for score in scores if score.submitted_rank == 1)
    winners_after = sorted(score.candidate for score in scores if score.replay_rank == 1)
    return RankingComparison(
        cutoff=cutoff,
        rows=len(submitted),
        scores=scores,
        submitted_winners=winners_before,
        replay_winners=winners_after,
        winner_changed=winners_before != winners_after,
    )
