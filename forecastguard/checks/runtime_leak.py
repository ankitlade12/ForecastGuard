"""Check 3 — Runtime leakage (behavioural perturbation). The moat.

A causal feature at time ``t`` cannot change when the future is hidden.
ForecastGuard builds a *future-masked* copy of the data — future-row targets and
undeclared (past-only) covariates set to NaN, while declared ``future_covariates``
and ``static_covariates`` are kept (they're genuinely known at predict time) —
re-runs ``spec.feature_fn`` on it, and diffs the **pre-cutoff** feature values
against the same features computed on the full frame. Any pre-cutoff value that
moves read across the cutoff: centered windows, full-frame scalers, whole-series
target encoders, and the like.

An observed change establishes future dependence behaviourally (D-003), including
cases source parsing misses. No observed change is bounded evidence for the tested
cutoff, mask, data, and tolerance; it is not a universal proof that no leakage
exists. Declared known-future covariates are preserved in the mask. See DECISIONS
D-013 and D-014.

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

from forecastguard.checks.forecast_leak import ForecastPerturbationCheck
from forecastguard.checks.protocol import CheckContext
from forecastguard.models.report import CheckResult, CheckStatus, Severity, Violation
from forecastguard.perturb import perturb_unknowns
from forecastguard.windows import window_cutoffs

_NUM_RTOL = 1e-5
_NUM_ATOL = 1e-8
_SAMPLE = 5  # changed rows recorded as evidence per leaking feature


class RuntimeLeakageCheck:
    """Behavioural-perturbation leakage detection — the differentiating check."""

    check_id = "runtime_leakage"
    name = "Runtime leakage"

    def run(self, ctx: CheckContext) -> CheckResult:
        """Aggregate configured feature- and forecast-level perturbations."""
        components: list[CheckResult] = []
        if ctx.feature_fn is not None:
            components.append(self._run_feature(ctx))
        if ctx.forecast_fn is not None:
            components.append(ForecastPerturbationCheck().run(ctx))
        if not components:
            return self._skip("no feature_fn or forecast_fn declared in spec — nothing to perturb")

        failures = [result for result in components if result.status is CheckStatus.FAIL]
        if failures:
            violations = [violation for result in failures for violation in result.violations]
            return CheckResult.failed(
                self.check_id,
                self.name,
                f"{len(violations)} runtime leakage violation(s)",
                violations,
            )
        skips = [result for result in components if result.status is CheckStatus.SKIPPED]
        if skips:
            reasons = "; ".join(result.detail or "unknown" for result in skips)
            return self._skip(f"runtime perturbation incomplete: {reasons}")
        return CheckResult.passed(
            self.check_id,
            self.name,
            "; ".join(result.summary for result in components),
        )

    def _run_feature(self, ctx: CheckContext) -> CheckResult:
        spec = ctx.spec
        frame = ctx.frame
        if ctx.feature_fn is None:
            return self._skip("no feature_fn declared in spec — nothing to perturb")
        if spec.id_col not in frame.columns or spec.time_col not in frame.columns:
            return self._skip("id/time column missing (the cutoff check reports this)")
        if spec.cutoff_col is not None:
            return self._skip(
                "cutoff_col input contains validation output, not raw history — "
                "runtime perturbation cannot compare pre-cutoff features"
            )

        try:
            pd.to_datetime(frame[spec.time_col], errors="raise")
            cutoffs = window_cutoffs(spec, frame)
        except (ValueError, TypeError, KeyError):
            return self._skip("can't parse timestamps/cutoff (the cutoff check reports this)")

        rolling = bool(spec.cutoffs)
        results = [self._run_window(ctx, cutoff, rolling=rolling) for cutoff in cutoffs]
        failures = [result for result in results if result.status is CheckStatus.FAIL]
        if failures:
            violations = [violation for result in failures for violation in result.violations]
            return CheckResult.failed(
                self.check_id,
                self.name,
                f"{len(violations)} feature/window leak(s) across {len(cutoffs)} window(s)",
                violations,
            )
        skipped = [result for result in results if result.status is CheckStatus.SKIPPED]
        if skipped:
            reasons = "; ".join(result.detail or "unknown precondition" for result in skipped[:3])
            return self._skip(
                f"{len(skipped)} of {len(cutoffs)} window(s) could not be evaluated: {reasons}"
            )
        if rolling:
            return CheckResult.passed(
                self.check_id,
                self.name,
                f"no future sensitivity detected across {len(cutoffs)} window(s) for the "
                "tested masks and tolerance",
            )
        return results[0]

    def _run_window(self, ctx: CheckContext, cutoff: pd.Timestamp, *, rolling: bool) -> CheckResult:
        spec = ctx.spec
        frame = ctx.frame
        feature_fn = ctx.feature_fn
        assert feature_fn is not None
        ds = pd.to_datetime(frame[spec.time_col], errors="raise")

        future_mask = ds > cutoff
        if not bool(future_mask.any()):
            return self._skip("no holdout rows after the cutoff — nothing to hide")
        if not bool((ds <= cutoff).any()):
            return self._skip("no pre-cutoff rows to compare")

        try:
            full_a = feature_fn(frame)
            full_b = feature_fn(frame)
        except Exception as exc:
            return self._skip(
                f"feature_fn raised ({type(exc).__name__}: {exc}) — cannot prove leakage"
            )

        full_pre = _pre_cutoff_features(full_a, spec, cutoff)
        repeat_pre = _pre_cutoff_features(full_b, spec, cutoff)
        if full_pre is None or repeat_pre is None:
            return self._skip(
                "feature_fn output must be a DataFrame with unique "
                f"({spec.id_col}, {spec.time_col}) rows including those columns"
            )
        if full_pre.empty or repeat_pre.empty:
            return self._skip("feature_fn output has no comparable pre-cutoff rows")
        if not full_pre.index.equals(repeat_pre.index):
            return self._skip("feature_fn output pre-cutoff rows do not align")
        if set(full_pre.columns) != set(repeat_pre.columns):
            return self._skip("feature_fn output feature columns do not align")

        nondeterministic = _changed_columns(full_pre, repeat_pre)
        if nondeterministic:
            cols = ", ".join(sorted(nondeterministic))
            return self._skip(
                f"feature_fn is nondeterministic (columns differ between runs: {cols}) "
                "— cannot prove leakage"
            )

        violations: list[Violation] = []
        shared_count = 0
        for mode_index, mode in enumerate(spec.perturbations):
            perturbed = perturb_unknowns(
                frame,
                spec,
                future_mask,
                mode,
                seed=spec.perturbation_seed + mode_index,
            )
            try:
                perturbed_out = feature_fn(perturbed)
            except Exception as exc:
                return self._skip(
                    f"feature_fn raised under {mode} ({type(exc).__name__}: {exc}) — "
                    "cannot prove leakage"
                )
            perturbed_pre = _pre_cutoff_features(perturbed_out, spec, cutoff)
            if perturbed_pre is None or perturbed_pre.empty:
                return self._skip("feature_fn perturbation output has no comparable rows")
            if not full_pre.index.equals(perturbed_pre.index):
                return self._skip("feature_fn output pre-cutoff rows do not align")
            if set(full_pre.columns) != set(perturbed_pre.columns):
                return self._skip("feature_fn output feature columns do not align")
            shared = [column for column in full_pre.columns if column in perturbed_pre.columns]
            shared_count = len(shared)
            if not shared:
                return self._skip("feature_fn produced no comparable feature columns")
            leaking = _changed_columns(full_pre[shared], perturbed_pre[shared])
            violations.extend(
                Violation(
                    code="FG-LEAK-001",
                    severity=Severity.CRITICAL,
                    message=f"feature {column!r} changes before the cutoff under {mode} "
                    "perturbation — it reads across the cutoff",
                    location=(f"{column}@{cutoff.isoformat()}" if rolling else str(column)),
                    evidence={
                        **detail,
                        "cutoff": cutoff.isoformat(),
                        "perturbation": mode,
                        **_hint_evidence(ctx, "feature"),
                    },
                )
                for column, detail in sorted(leaking.items())
            )

        if violations:
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
            f"no future sensitivity detected in {shared_count} feature(s) for this cutoff, "
            f"mask, and tolerance ({pre_rows} pre-cutoff rows compared)",
        )

    def _skip(self, reason: str) -> CheckResult:
        return CheckResult.skipped(self.check_id, self.name, reason)


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


def _hint_evidence(ctx: CheckContext, component: str) -> dict[str, object]:
    hints = [
        hint.model_dump(mode="json") for hint in ctx.source_hints if hint.component == component
    ]
    return {"source_hints": hints} if hints else {}
