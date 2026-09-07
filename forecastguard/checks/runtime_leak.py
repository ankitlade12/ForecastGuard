"""Feature and forecast sensitivity to unavailable future inputs.

Compare isolated executions at each configured origin. A detected dependency is
FAIL; incomplete probes remain visible. PASS is bounded to the tested inputs,
windows, modes and tolerances."""

from __future__ import annotations

import pandas as pd

from forecastguard.checks.comparison import aggregate, indexed_output, same_shape
from forecastguard.checks.comparison import changed_columns as _changed_columns
from forecastguard.checks.forecast_leak import ForecastPerturbationCheck
from forecastguard.checks.protocol import CheckContext
from forecastguard.models.report import CheckResult, CheckStatus, Severity, Violation
from forecastguard.models.spec import ForecastSpec
from forecastguard.perturb import perturb_unknowns


class RuntimeLeakageCheck:
    """Behavioural-perturbation leakage detection — the differentiating check."""

    check_id = "runtime_leakage"
    name = "Runtime leakage"

    def run(self, ctx: CheckContext) -> CheckResult:
        """Aggregate configured feature- and forecast-level perturbations."""
        budget = self.check_budget(
            ctx, int(ctx.feature_fn is not None) + int(ctx.forecast_fn is not None)
        )
        if budget is not None:
            return budget
        components: list[CheckResult] = []
        if ctx.feature_fn is not None:
            components.append(self._run_feature(ctx))
        if ctx.forecast_fn is not None:
            components.append(ForecastPerturbationCheck().run(ctx))
        if not components:
            return self._skip("no feature_fn or forecast_fn declared in spec — nothing to perturb")

        result = aggregate(components, "; ".join(part.summary for part in components))
        if result.status is CheckStatus.PASS:
            result.summary = "no future sensitivity detected; " + result.summary
        return result

    def check_budget(self, ctx: CheckContext, callable_count: int) -> CheckResult | None:
        spec = ctx.spec
        if spec.max_probe_calls is None or spec.cutoff_col is not None or not callable_count:
            return None
        calls = len(ctx.windows.origins) * (2 + len(spec.perturbations)) * callable_count
        if calls > spec.max_probe_calls:
            return self._skip(
                f"runtime requires up to {calls} callable executions; "
                f"max_probe_calls={spec.max_probe_calls}; no probes executed"
            )
        return None

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
            cutoffs = [cutoff for cutoff, _ in ctx.windows.origins]
        except (ValueError, TypeError, KeyError):
            return self._skip("can't parse timestamps/cutoff (the cutoff check reports this)")

        rolling = bool(spec.cutoffs)
        results = [self._run_window(ctx, cutoff, rolling=rolling) for cutoff in cutoffs]
        return aggregate(
            results,
            f"feature probes: {len(cutoffs)} window(s), {len(spec.perturbations)} mode(s) requested",
        )

    def _run_window(self, ctx: CheckContext, cutoff: pd.Timestamp, *, rolling: bool) -> CheckResult:
        spec = ctx.spec
        frame = ctx.frame
        feature_fn = ctx.feature_fn
        assert feature_fn is not None
        ds = ctx.windows.timestamps

        future_mask = ds > cutoff
        if not bool(future_mask.any()):
            return self._skip("no holdout rows after the cutoff — nothing to hide")
        if not bool((ds <= cutoff).any()):
            return self._skip("no pre-cutoff rows to compare")

        try:
            full_pre = _pre_cutoff_features(feature_fn(frame.copy(deep=True)), spec, cutoff)
            repeat_pre = _pre_cutoff_features(feature_fn(frame.copy(deep=True)), spec, cutoff)
        except Exception as exc:
            return self._skip(
                f"feature_fn raised ({type(exc).__name__}: {exc}) — cannot prove leakage"
            )

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
        probes: list[CheckResult] = []
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
                probes.append(
                    self._skip(f"{cutoff.isoformat()}/{mode}: {type(exc).__name__}: {exc}")
                )
                continue
            perturbed_pre = _pre_cutoff_features(perturbed_out, spec, cutoff)
            if perturbed_pre is None or perturbed_pre.empty:
                probes.append(
                    self._skip(
                        f"{cutoff.isoformat()}/{mode}: feature_fn perturbation output has no comparable rows"
                    )
                )
                continue
            if not same_shape(full_pre, perturbed_pre):
                probes.append(
                    self._skip(
                        f"{cutoff.isoformat()}/{mode}: feature_fn output rows or feature columns do not align"
                    )
                )
                continue
            probes.append(
                CheckResult.passed(
                    self.check_id, self.name, f"{cutoff.isoformat()}/{mode} completed"
                )
            )
            leaking = _changed_columns(full_pre, perturbed_pre)
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
            probes.append(
                CheckResult.failed(
                    self.check_id, self.name, "future sensitivity detected", violations
                )
            )
        return aggregate(
            probes,
            f"{len(violations)} violation(s); {len(full_pre.columns)} feature(s), "
            f"{len(full_pre)} pre-cutoff rows, {len(spec.perturbations)} mode(s) requested",
        )

    def _skip(self, reason: str) -> CheckResult:
        return CheckResult.skipped(self.check_id, self.name, reason)


def _pre_cutoff_features(
    out: object, spec: ForecastSpec, cutoff: pd.Timestamp
) -> pd.DataFrame | None:
    indexed = indexed_output(out, spec.id_col, spec.time_col)
    if indexed is None:
        return None
    return indexed.loc[indexed.index.get_level_values(spec.time_col) <= cutoff]


def _hint_evidence(ctx: CheckContext, component: str) -> dict[str, object]:
    hints = [
        hint.model_dump(mode="json") for hint in ctx.source_hints if hint.component == component
    ]
    return {"source_hints": hints} if hints else {}
