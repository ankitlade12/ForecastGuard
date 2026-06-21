"""Check 3 — Runtime leakage (behavioural perturbation). The moat.

A leak-free feature at time ``t`` cannot change when the future is hidden.
ForecastGuard builds a *future-masked* copy of the data — future-row targets and
undeclared (past-only) covariates set to NaN, while declared ``future_covariates``
and ``static_covariates`` are kept (they're genuinely known at predict time) —
re-runs ``spec.feature_fn`` on it, and diffs the **pre-cutoff** feature values
against the same features computed on the full frame. Any pre-cutoff value that
moves read across the cutoff: centered windows, full-frame scalers, whole-series
target encoders, and the like.

It proves leakage *behaviourally* (D-003): it catches what source parsing misses
and never false-positives on a correctly-built trailing feature — or on a
forward-looking feature over a *declared* known-future covariate (that column is
preserved in the mask). See DECISIONS D-013.

Honest scope — this check SKIPS LOUDLY (never passes silently) whenever it can't
prove anything: no ``feature_fn``; no holdout to hide; the function raising; an
output it can't align; or a nondeterministic ``feature_fn``.

Violation: ``FG-LEAK-001`` — a feature changes before the cutoff when the future
is hidden (CRITICAL), one per leaking feature column.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype

from forecastguard.checks.protocol import CheckContext
from forecastguard.models.report import CheckResult, Severity, Violation

_NUM_RTOL = 1e-5
_NUM_ATOL = 1e-8
_SAMPLE = 5  # changed rows recorded as evidence per leaking feature


class RuntimeLeakageCheck:
    """Behavioural-perturbation leakage detection — the differentiating check."""

    check_id = "runtime_leakage"
    name = "Runtime leakage"

    def run(self, ctx: CheckContext) -> CheckResult:
        spec = ctx.spec
        frame = ctx.frame
        feature_fn = ctx.feature_fn

        if feature_fn is None:
            return self._skip("no feature_fn declared in spec — nothing to perturb")
        if spec.id_col not in frame.columns or spec.time_col not in frame.columns:
            return self._skip("id/time column missing (the cutoff check reports this)")

        try:
            ds = pd.to_datetime(frame[spec.time_col], errors="raise")
            cutoff = pd.Timestamp(spec.cutoff)
        except (ValueError, TypeError):
            return self._skip("can't parse timestamps/cutoff (the cutoff check reports this)")

        future_mask = ds > cutoff
        if not bool(future_mask.any()):
            return self._skip("no holdout rows after the cutoff — nothing to hide")
        if not bool((ds <= cutoff).any()):
            return self._skip("no pre-cutoff rows to compare")

        masked = _mask_future(frame, spec, future_mask)

        try:
            full_a = feature_fn(frame)
            full_b = feature_fn(frame)
            masked_out = feature_fn(masked)
        except Exception as exc:
            return self._skip(
                f"feature_fn raised ({type(exc).__name__}: {exc}) — cannot prove leakage"
            )

        full_pre = _pre_cutoff_features(full_a, spec, cutoff)
        repeat_pre = _pre_cutoff_features(full_b, spec, cutoff)
        masked_pre = _pre_cutoff_features(masked_out, spec, cutoff)
        if full_pre is None or repeat_pre is None or masked_pre is None:
            return self._skip(
                "feature_fn output must be a DataFrame with unique "
                f"({spec.id_col}, {spec.time_col}) rows including those columns"
            )
        if full_pre.empty or repeat_pre.empty or masked_pre.empty:
            return self._skip("feature_fn output has no comparable pre-cutoff rows")
        if not full_pre.index.equals(repeat_pre.index) or not full_pre.index.equals(
            masked_pre.index
        ):
            return self._skip("feature_fn output pre-cutoff rows do not align")
        if set(full_pre.columns) != set(repeat_pre.columns) or set(full_pre.columns) != set(
            masked_pre.columns
        ):
            return self._skip("feature_fn output feature columns do not align")

        nondeterministic = _changed_columns(full_pre, repeat_pre)
        if nondeterministic:
            cols = ", ".join(sorted(nondeterministic))
            return self._skip(
                f"feature_fn is nondeterministic (columns differ between runs: {cols}) "
                "— cannot prove leakage"
            )

        shared = [c for c in full_pre.columns if c in masked_pre.columns]
        if not shared:
            return self._skip("feature_fn produced no comparable feature columns")

        leaking = _changed_columns(full_pre[shared], masked_pre[shared])
        if leaking:
            violations = [
                Violation(
                    code="FG-LEAK-001",
                    severity=Severity.CRITICAL,
                    message=f"feature {col!r} changes before the cutoff when the future is "
                    "hidden — it reads across the cutoff",
                    location=str(col),
                    evidence=detail,
                )
                for col, detail in sorted(leaking.items())
            ]
            count = len(violations)
            return CheckResult.failed(
                self.check_id,
                self.name,
                f"{count} feature(s) leak across the cutoff",
                violations,
            )

        pre_rows = len(full_pre)
        return CheckResult.passed(
            self.check_id,
            self.name,
            f"{len(shared)} feature(s) are leak-free across the cutoff "
            f"(perturbation diff over {pre_rows} pre-cutoff rows)",
        )

    def _skip(self, reason: str) -> CheckResult:
        return CheckResult.skipped(self.check_id, self.name, reason)


def _mask_future(frame: pd.DataFrame, spec: object, future_mask: pd.Series) -> pd.DataFrame:
    """Copy the frame with future-row unknowns set to NaN.

    Kept (known at predict time): id, time, declared future + static covariates.
    Masked: the target and every other (past-only) covariate.
    """
    keep = {spec.id_col, spec.time_col, *spec.future_covariates, *spec.static_covariates}  # type: ignore[attr-defined]
    mask_cols = [c for c in frame.columns if c not in keep]
    masked = frame.copy()
    for col in mask_cols:
        masked[col] = masked[col].mask(future_mask)
    return masked


def _pre_cutoff_features(out: object, spec: object, cutoff: pd.Timestamp) -> pd.DataFrame | None:
    """Index a feature-fn output by ``(id, ds)`` over pre-cutoff rows, or None if unalignable."""
    if not isinstance(out, pd.DataFrame):
        return None
    id_col, time_col = spec.id_col, spec.time_col  # type: ignore[attr-defined]
    if id_col not in out.columns or time_col not in out.columns:
        return None
    ds = pd.to_datetime(out[time_col], errors="coerce")
    feature_cols = [c for c in out.columns if c not in (id_col, time_col)]
    indexed = out.assign(__fg_ds=ds).loc[ds <= cutoff].set_index([id_col, "__fg_ds"])[feature_cols]
    if indexed.index.has_duplicates:
        return None
    return indexed.sort_index()


def _changed_columns(a: pd.DataFrame, b: pd.DataFrame) -> dict[str, dict[str, object]]:
    """Columns whose aligned values differ between two pre-cutoff feature frames."""
    idx = a.index.intersection(b.index)
    changed: dict[str, dict[str, object]] = {}
    for col in (c for c in a.columns if c in b.columns):
        av = a.loc[idx, col]
        bv = b.loc[idx, col]
        if is_numeric_dtype(av) and is_numeric_dtype(bv):
            diff = ~np.isclose(
                av.to_numpy(dtype=float),
                bv.to_numpy(dtype=float),
                rtol=_NUM_RTOL,
                atol=_NUM_ATOL,
                equal_nan=True,
            )
        else:
            ne = av.ne(bv).to_numpy()
            both_na = (av.isna() & bv.isna()).to_numpy()
            diff = ne & ~both_na
        if not bool(diff.any()):
            continue
        changed_keys = [key for key, is_diff in zip(idx, diff, strict=True) if is_diff]
        sample = [
            {
                "id": str(key[0]),
                "ds": pd.Timestamp(key[1]).isoformat(),
                "full": _scalar(av.loc[key]),
                "masked": _scalar(bv.loc[key]),
            }
            for key in changed_keys[:_SAMPLE]
        ]
        changed[col] = {"changed_pre_cutoff_rows": int(diff.sum()), "sample": sample}
    return changed


def _scalar(value: object) -> object:
    """JSON-friendly scalar for evidence."""
    if pd.isna(value):
        return None
    item = getattr(value, "item", None)
    if callable(item):
        return item()
    return value if isinstance(value, (int, float, str, bool)) else str(value)
