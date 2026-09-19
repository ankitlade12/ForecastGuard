"""Forecast-output behavioural perturbation used by the runtime check."""

from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype

from forecastguard.checks.comparison import aggregate, changed_columns
from forecastguard.checks.comparison import indexed_output as _prediction_frame
from forecastguard.checks.comparison import same_shape as _same_shape
from forecastguard.checks.protocol import CheckContext
from forecastguard.execution import finish_coverage, invoke_forecast, mark_probe
from forecastguard.models.execution import Component
from forecastguard.models.report import CheckResult, Severity, Violation
from forecastguard.perturb import perturb_unknowns


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
            windows = ctx.windows
        except (ValueError, TypeError, KeyError):
            return self._skip("can't parse timestamps/window configuration")

        component: Component = "pipeline" if spec.pipeline_factory else "forecast"
        results = []
        for index, (cutoff, expected) in enumerate(windows.origins):
            result = self._run_window(ctx, windows.timestamps, cutoff, expected, index)
            finish_coverage(
                ctx, result.detail or result.summary, component=component, cutoff=cutoff
            )
            results.append(result)
        return aggregate(
            results,
            f"{len(windows.origins)} forecast window(s), {len(spec.perturbations)} mode(s) requested",
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
            aligned_a = _prediction_frame(
                invoke_forecast(ctx, train.copy(), future.copy(), cutoff),
                spec.id_col,
                spec.time_col,
            )
            aligned_b = _prediction_frame(
                invoke_forecast(ctx, train.copy(), future.copy(), cutoff),
                spec.id_col,
                spec.time_col,
            )
        except Exception as exc:
            return self._skip(
                f"forecast_fn raised at cutoff {cutoff.isoformat()} ({type(exc).__name__}: {exc})"
            )
        if aligned_a is None or aligned_b is None or not _same_shape(aligned_a, aligned_b):
            return self._skip("forecast_fn outputs are unalignable or inconsistent")
        expected_keys = pd.MultiIndex.from_product(
            [ctx.frame[spec.id_col].unique(), expected], names=[spec.id_col, spec.time_col]
        ).sort_values()
        if not aligned_a.index.equals(expected_keys):
            return self._skip(
                "forecast_fn must return every expected series/horizon row exactly once"
            )
        for baseline in (aligned_a, aligned_b):
            if any(not is_numeric_dtype(baseline[column]) for column in baseline):
                return self._skip("forecast_fn baseline predictions must be numeric")
            if not np.isfinite(baseline.to_numpy(dtype=float, na_value=np.nan)).all():
                return self._skip("forecast_fn baseline contains missing or non-finite predictions")
        nondeterministic = _changed_predictions(aligned_a, aligned_b)
        if nondeterministic:
            return self._skip("forecast_fn is nondeterministic — cannot attribute sensitivity")

        violations: list[Violation] = []
        probes: list[CheckResult] = []
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
                candidate = invoke_forecast(ctx, train.copy(), perturbed, cutoff)
            except Exception as exc:
                probes.append(
                    self._skip(f"{cutoff.isoformat()}/{mode}: {type(exc).__name__}: {exc}")
                )
                continue
            aligned = _prediction_frame(candidate, spec.id_col, spec.time_col)
            if aligned is None or not _same_shape(aligned_a, aligned):
                probes.append(
                    self._skip(f"{cutoff.isoformat()}/{mode}: forecast_fn output changed shape")
                )
                continue
            probes.append(
                CheckResult.passed(
                    self.check_id, self.name, f"{cutoff.isoformat()}/{mode} completed"
                )
            )
            changed = _changed_predictions(aligned_a, aligned)
            mark_probe(
                ctx,
                "pipeline" if spec.pipeline_factory else "forecast",
                cutoff,
                mode,
                failed=bool(changed),
                rows=len(aligned_a),
            )
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
            probes.append(
                CheckResult.failed(
                    self.check_id, self.name, "future sensitivity detected", violations
                )
            )
        return aggregate(
            probes,
            f"{cutoff.isoformat()}: {len(violations)} violation(s), "
            f"{len(aligned_a)} prediction rows",
        )

    def _skip(self, reason: str) -> CheckResult:
        return CheckResult.skipped(self.check_id, self.name, reason)


def _changed_predictions(
    baseline: pd.DataFrame, candidate: pd.DataFrame
) -> dict[str, dict[str, object]]:
    return changed_columns(
        baseline,
        candidate,
        count_key="changed_prediction_rows",
        baseline_key="baseline",
        candidate_key="perturbed",
    )


def _hint_evidence(ctx: CheckContext) -> dict[str, object]:
    hints = [
        hint.model_dump(mode="json") for hint in ctx.source_hints if hint.component == "forecast"
    ]
    return {"source_hints": hints} if hints else {}
