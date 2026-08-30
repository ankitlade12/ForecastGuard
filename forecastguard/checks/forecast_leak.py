"""Forecast-output behavioural perturbation used by the runtime check."""

from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype
from pandas.tseries.frequencies import to_offset

from forecastguard.checks.protocol import CheckContext
from forecastguard.models.report import CheckResult, CheckStatus, Severity, Violation
from forecastguard.perturb import perturb_unknowns
from forecastguard.windows import forecast_grid, window_cutoffs

_RTOL = 1e-5
_ATOL = 1e-8
_SAMPLE = 5


class ForecastPerturbationCheck:
    """Evaluate whether hidden/unavailable future inputs change predictions."""

    check_id = "runtime_leakage"
    name = "Runtime leakage"

    def run(self, ctx: CheckContext) -> CheckResult:
        spec = ctx.spec
        if ctx.forecast_fn is None:
            return self._skip("no forecast_fn declared")
        if spec.cutoff_col is not None:
            return self._skip("cutoff_col input has no raw training history for forecast_fn")
        if spec.id_col not in ctx.frame.columns or spec.time_col not in ctx.frame.columns:
            return self._skip("id/time column missing (the cutoff check reports this)")
        try:
            ds = pd.to_datetime(ctx.frame[spec.time_col], errors="raise")
            cutoffs = window_cutoffs(spec, ctx.frame)
            offset = to_offset(spec.freq)
        except (ValueError, TypeError, KeyError):
            return self._skip("can't parse timestamps/window configuration")

        results = [
            self._run_window(ctx, ds, cutoff, forecast_grid(cutoff, offset, spec.horizon), index)
            for index, cutoff in enumerate(cutoffs)
        ]
        failures = [result for result in results if result.status is CheckStatus.FAIL]
        if failures:
            violations = [violation for result in failures for violation in result.violations]
            return CheckResult.failed(
                self.check_id,
                self.name,
                f"{len(violations)} forecast-output sensitivity violation(s)",
                violations,
            )
        skips = [result for result in results if result.status is CheckStatus.SKIPPED]
        if skips:
            reasons = "; ".join(result.detail or "unknown" for result in skips[:3])
            return self._skip(f"forecast perturbation incomplete: {reasons}")
        return CheckResult.passed(
            self.check_id,
            self.name,
            f"forecast outputs stable across {len(cutoffs)} window(s) and "
            f"{len(spec.perturbations)} perturbation mode(s)",
        )

    def _run_window(
        self,
        ctx: CheckContext,
        ds: pd.Series,
        cutoff: pd.Timestamp,
        expected: list[pd.Timestamp],
        window_index: int,
    ) -> CheckResult:
        spec = ctx.spec
        forecast_fn = ctx.forecast_fn
        assert forecast_fn is not None
        train = ctx.frame.loc[ds.le(cutoff)].copy()
        future_mask = ds.gt(cutoff) & ds.le(expected[-1])
        future = ctx.frame.loc[future_mask].copy()
        if train.empty or future.empty:
            return self._skip(f"empty train/future input at cutoff {cutoff.isoformat()}")
        try:
            baseline_a = forecast_fn(train.copy(), future.copy())
            baseline_b = forecast_fn(train.copy(), future.copy())
        except Exception as exc:
            return self._skip(
                f"forecast_fn raised at cutoff {cutoff.isoformat()} ({type(exc).__name__}: {exc})"
            )
        aligned_a = _prediction_frame(baseline_a, spec.id_col, spec.time_col)
        aligned_b = _prediction_frame(baseline_b, spec.id_col, spec.time_col)
        if aligned_a is None or aligned_b is None or not _same_shape(aligned_a, aligned_b):
            return self._skip("forecast_fn outputs are unalignable or inconsistent")
        nondeterministic = _changed_predictions(aligned_a, aligned_b)
        if nondeterministic:
            return self._skip("forecast_fn is nondeterministic — cannot attribute sensitivity")

        violations: list[Violation] = []
        all_rows = pd.Series(True, index=future.index)
        for mode_index, mode in enumerate(spec.perturbations):
            perturbed = perturb_unknowns(
                future,
                spec,
                all_rows,
                mode,
                seed=spec.perturbation_seed + window_index * 1009 + mode_index,
            )
            try:
                candidate = forecast_fn(train.copy(), perturbed)
            except Exception as exc:
                return self._skip(
                    f"forecast_fn raised under {mode} at {cutoff.isoformat()} "
                    f"({type(exc).__name__}: {exc})"
                )
            aligned = _prediction_frame(candidate, spec.id_col, spec.time_col)
            if aligned is None or not _same_shape(aligned_a, aligned):
                return self._skip(f"forecast_fn output changed shape under {mode}")
            changed = _changed_predictions(aligned_a, aligned)
            for column, detail in sorted(changed.items()):
                violations.append(
                    Violation(
                        code="FG-FORECAST-001",
                        severity=Severity.CRITICAL,
                        message=f"prediction {column!r} changes when unavailable future inputs "
                        f"are perturbed with {mode}",
                        location=f"{column}@{cutoff.isoformat()}",
                        evidence={
                            **detail,
                            "cutoff": cutoff.isoformat(),
                            "perturbation": mode,
                            "prediction_column": str(column),
                            **_hint_evidence(ctx),
                        },
                    )
                )
        if violations:
            return CheckResult.failed(
                self.check_id,
                self.name,
                f"{len(violations)} sensitive forecast output(s)",
                violations,
            )
        return CheckResult.passed(self.check_id, self.name, "forecast output stable")

    def _skip(self, reason: str) -> CheckResult:
        return CheckResult.skipped(self.check_id, self.name, reason)


def _prediction_frame(out: object, id_col: str, time_col: str) -> pd.DataFrame | None:
    if not isinstance(out, pd.DataFrame) or id_col not in out or time_col not in out:
        return None
    prediction_cols = [column for column in out.columns if column not in (id_col, time_col)]
    if not prediction_cols:
        return None
    ds = pd.to_datetime(out[time_col], errors="coerce")
    if bool(ds.isna().any()):
        return None
    indexed = out.assign(__fg_ds=ds).set_index([id_col, "__fg_ds"])[prediction_cols]
    if indexed.index.has_duplicates:
        return None
    return indexed.sort_index()


def _same_shape(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    return left.index.equals(right.index) and set(left.columns) == set(right.columns)


def _changed_predictions(
    baseline: pd.DataFrame, candidate: pd.DataFrame
) -> dict[str, dict[str, object]]:
    changed: dict[str, dict[str, object]] = {}
    for column in baseline.columns:
        left = baseline[column]
        right = candidate[column]
        if is_numeric_dtype(left) and is_numeric_dtype(right):
            mask = ~np.isclose(
                left.to_numpy(dtype=float),
                right.to_numpy(dtype=float),
                rtol=_RTOL,
                atol=_ATOL,
                equal_nan=True,
            )
        else:
            mask = left.ne(right).to_numpy() & ~(left.isna() & right.isna()).to_numpy()
        if not bool(mask.any()):
            continue
        keys = [key for key, value in zip(left.index, mask, strict=True) if value]
        changed[str(column)] = {
            "changed_prediction_rows": int(mask.sum()),
            "sample": [
                {
                    "id": str(key[0]),
                    "ds": pd.Timestamp(key[1]).isoformat(),
                    "baseline": _scalar(left.loc[key]),
                    "perturbed": _scalar(right.loc[key]),
                }
                for key in keys[:_SAMPLE]
            ],
        }
    return changed


def _scalar(value: object) -> object:
    if pd.isna(value):
        return None
    item = getattr(value, "item", None)
    if callable(item):
        return item()
    return value if isinstance(value, (int, float, str, bool)) else str(value)


def _hint_evidence(ctx: CheckContext) -> dict[str, object]:
    hints = [
        hint.model_dump(mode="json") for hint in ctx.source_hints if hint.component == "forecast"
    ]
    return {"source_hints": hints} if hints else {}
