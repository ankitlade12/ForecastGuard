"""Budgeted, explanation-only single-input interventions after proven sensitivity."""

from collections.abc import Callable

import numpy as np
import pandas as pd

from forecastguard.checks.comparison import changed_columns, indexed_output, same_shape
from forecastguard.checks.protocol import CheckContext
from forecastguard.execution import invoke_feature, invoke_forecast
from forecastguard.models.execution import Component, Diagnostic
from forecastguard.models.report import CheckResult
from forecastguard.perturb import perturb_unknowns


def diagnose(ctx: CheckContext, result: CheckResult) -> None:
    """Append diagnostics without modifying results, violations or primary coverage."""
    spec = ctx.spec
    remaining = spec.max_diagnostic_calls
    if spec.max_probe_calls is not None:
        remaining = min(remaining, max(0, spec.max_probe_calls - ctx.runtime_calls))
    groups: set[tuple[Component, str]] = set()
    for violation in result.violations:
        component: Component
        if violation.code == "FG-LEAK-001":
            component = "feature"
        elif violation.code == "FG-FORECAST-001":
            component = "pipeline" if spec.pipeline_factory else "forecast"
        else:
            continue
        cutoff = violation.evidence.get("cutoff")
        if isinstance(cutoff, str):
            groups.add((component, cutoff))

    def call(fn: Callable[[], pd.DataFrame]) -> pd.DataFrame:
        nonlocal remaining
        if remaining <= 0:
            raise ValueError("diagnostic call budget exhausted; remaining inputs are untested")
        remaining -= 1
        ctx.diagnostic_calls += 1
        return fn()

    for component, origin in sorted(groups):
        cutoff = pd.Timestamp(origin)
        if remaining < 3:
            ctx.diagnostics.append(
                Diagnostic(
                    component=component,
                    cutoff=origin,
                    status="skipped",
                    detail="insufficient diagnostic budget for two baseline runs and one input intervention",
                )
            )
            continue
        ds = ctx.windows.timestamps
        if component == "feature":
            frame = ctx.frame
            mask = ds.gt(cutoff)

            def execute(data: pd.DataFrame, training: pd.DataFrame | None = None) -> pd.DataFrame:
                return invoke_feature(ctx, data.copy(deep=True))
        else:
            expected = next(grid for value, grid in ctx.windows.origins if value == cutoff)
            train = ctx.frame.loc[ds.le(cutoff)].copy()
            frame = ctx.frame.loc[ds.isin(expected)].copy()
            mask = pd.Series(True, index=frame.index)

            def execute(data: pd.DataFrame, training: pd.DataFrame | None = train) -> pd.DataFrame:
                assert training is not None
                return invoke_forecast(ctx, training.copy(deep=True), data.copy(deep=True))

        def aligned(
            data: pd.DataFrame, boundary: Component = component, anchor: pd.Timestamp = cutoff
        ) -> pd.DataFrame:
            indexed = indexed_output(call(lambda: execute(data)), spec.id_col, spec.time_col)
            if indexed is None:
                raise ValueError("diagnostic output is empty or unalignable")
            if boundary == "feature":
                indexed = indexed.loc[indexed.index.get_level_values(spec.time_col) <= anchor]
            return indexed

        try:
            baseline, repeat = aligned(frame), aligned(frame)
            if (
                baseline.empty
                or not same_shape(baseline, repeat)
                or changed_columns(baseline, repeat)
            ):
                raise ValueError("diagnostic baseline is empty, unalignable or nondeterministic")
            if component != "feature" and not np.isfinite(baseline.to_numpy(dtype=float)).all():
                raise ValueError("diagnostic baseline predictions are non-finite")
        except Exception as exc:
            ctx.diagnostics.append(
                Diagnostic(
                    component=component,
                    cutoff=origin,
                    status="skipped",
                    detail=f"diagnostic baseline unavailable: {type(exc).__name__}: {exc}",
                )
            )
            continue
        keep = {
            spec.id_col,
            spec.time_col,
            spec.cutoff_col,
            *spec.future_covariates,
            *spec.static_covariates,
        }
        inputs = [str(column) for column in frame.columns if column not in keep]
        for mode_index, mode in enumerate(spec.perturbations):
            for column in inputs:
                if remaining <= 0:
                    ctx.diagnostics.append(
                        Diagnostic(
                            component=component,
                            cutoff=origin,
                            status="skipped",
                            input_column=column,
                            mode=mode,
                            detail="diagnostic call budget exhausted; this and remaining inputs are untested",
                        )
                    )
                    break
                try:
                    perturbed = perturb_unknowns(
                        frame,
                        spec,
                        mask,
                        mode,
                        seed=spec.perturbation_seed + mode_index,
                        columns=[column],
                    )
                    candidate = aligned(perturbed)
                    if not same_shape(baseline, candidate):
                        raise ValueError("input intervention changed output shape")
                    changed = changed_columns(baseline, candidate)
                    ctx.diagnostics.append(
                        Diagnostic(
                            component=component,
                            cutoff=origin,
                            input_column=column,
                            mode=mode,
                            status="sensitive" if changed else "unchanged",
                            outputs=sorted(changed),
                            detail=f"Only {column!r} was perturbed; "
                            + (
                                "outputs changed."
                                if changed
                                else "no change observed in this intervention."
                            ),
                            suggestion=(
                                "Remove actual future targets from prediction inputs; inspect recursive horizon features."
                                if column == spec.target_col
                                else "Verify when this input was available; use archived forecasts or a causal lag inside the tested pipeline."
                            )
                            if changed
                            else None,
                        )
                    )
                except Exception as exc:
                    ctx.diagnostics.append(
                        Diagnostic(
                            component=component,
                            cutoff=origin,
                            input_column=column,
                            mode=mode,
                            status="skipped",
                            detail=f"{type(exc).__name__}: {exc}",
                        )
                    )
            if remaining <= 0:
                break
