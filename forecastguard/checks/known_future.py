"""Check 2 — Known-future covariates (declared availability contract).

A covariate consumed at predict time that won't exist in production is leakage in
disguise. The user *declares* which covariates are known-at-predict-time via
``spec.future_covariates``; this check validates that availability declaration
against the data. It does not yet inspect which columns a model consumes.

Why this is a contract check, not a behavioural one (see DECISIONS D-012): from a
historical backtest panel alone you cannot tell a future covariate (e.g. a planned
promo) from a past one (e.g. actual weather) — both have values after the cutoff,
because the backtest needs those actuals to score against. So flagging "undeclared
covariate has future values" would false-positive on every legitimate past
covariate. Instead this check validates the *declared* contract deterministically,
and surfaces the undeclared covariates for the user to confirm. The behavioural
proof that an undeclared covariate actually leaks is the runtime check (Slice 4).

Violations:

* ``FG-FUTURE-001`` — a declared future covariate is not a column in the data (HIGH)
* ``FG-FUTURE-002`` — a declared future covariate has no values anywhere in the
  holdout window, so it provides no future information there (HIGH)
* ``FG-FUTURE-003`` — a declared future covariate has partial holdout coverage
  across the available series/timestamps (HIGH)
* ``FG-FUTURE-004`` — the fitted adapter consumes a raw covariate that is not
  declared future-known or static (CRITICAL)
* ``FG-AVAIL-001`` — availability timestamp column is missing/unparseable (HIGH)
* ``FG-AVAIL-002`` — a value was not available at its historical event time or
  at the forecast origin where it is used (CRITICAL)
* ``FG-STATIC-001`` — a declared static covariate is not a column (HIGH)
* ``FG-STATIC-002`` — a declared static covariate changes within a series (HIGH)

Undeclared covariate columns are reported in the PASS summary as "past-only", not
as failures.
"""

from __future__ import annotations

import pandas as pd

from forecastguard.checks.protocol import CheckContext
from forecastguard.checks.revisions import check_revisions
from forecastguard.models.report import CheckResult, CheckStatus, Severity, Violation
from forecastguard.windows import holdout_mask


class KnownFutureCovariatesCheck:
    """Validates the declared future-covariate contract against the data."""

    check_id = "known_future_covariates"
    name = "Known-future covariates"

    def run(self, ctx: CheckContext) -> CheckResult:
        spec = ctx.spec
        frame = ctx.frame
        column_set = set(frame.columns)

        reserved = {spec.id_col, spec.time_col, spec.target_col, *spec.static_covariates}
        if spec.cutoff_col is not None:
            reserved.add(spec.cutoff_col)
        reserved.update(item.available_at_col for item in spec.availability)
        covariate_cols = [c for c in frame.columns if c not in reserved]
        declared = list(dict.fromkeys(spec.future_covariates))  # dedupe, keep order

        violations: list[Violation] = []

        if ctx.adapter_usage is not None:
            declared_available = {*spec.future_covariates, *spec.static_covariates}
            for name in ctx.adapter_usage.consumed_covariates:
                if name in declared_available:
                    continue
                violations.append(
                    Violation(
                        code="FG-FUTURE-004",
                        severity=Severity.CRITICAL,
                        message=f"{ctx.adapter_usage.adapter} consumes raw covariate {name!r}, "
                        "but it is not declared future-known or static",
                        location=name,
                        evidence={
                            "adapter": ctx.adapter_usage.adapter,
                            "feature_order": ctx.adapter_usage.feature_order,
                        },
                    )
                )

        # FG-FUTURE-001 — declared future covariate isn't even a column.
        for name in (d for d in declared if d not in column_set):
            violations.append(
                Violation(
                    code="FG-FUTURE-001",
                    severity=Severity.HIGH,
                    message=f"declared future covariate {name!r} is not a column in the data",
                    location=name,
                    evidence={"available_columns": [str(c) for c in frame.columns]},
                )
            )

        # Static declarations are part of the same predict-time information
        # contract. Missing or time-varying "static" columns would be preserved
        # by the runtime mask, so validate that trust assumption explicitly.
        windows = _holdout_windows(ctx)
        for name in spec.static_covariates:
            if name not in column_set:
                violations.append(
                    Violation(
                        code="FG-STATIC-001",
                        severity=Severity.HIGH,
                        message=f"declared static covariate {name!r} is not a column in the data",
                        location=name,
                        evidence={"available_columns": [str(c) for c in frame.columns]},
                    )
                )
                continue
            if spec.id_col not in column_set:
                continue
            cardinality = frame.groupby(spec.id_col, dropna=False)[name].nunique(dropna=False)
            affected = sorted(str(series_id) for series_id in cardinality[cardinality > 1].index)
            if affected:
                violations.append(
                    Violation(
                        code="FG-STATIC-002",
                        severity=Severity.HIGH,
                        message=f"declared static covariate {name!r} changes within a series",
                        location=name,
                        evidence={
                            "affected_series": affected[:50],
                            "affected_series_count": len(affected),
                        },
                    )
                )

        violations.extend(_availability_violations(ctx, windows=windows))

        # FG-FUTURE-002 — declared future covariate is absent across the holdout.
        present_declared = [d for d in declared if d in column_set]
        holdout_checked = False
        rolling = spec.cutoff_col is not None or bool(spec.cutoffs)
        for cutoff, holdout in windows:
            if not bool(holdout.any()):
                continue
            holdout_checked = True
            for name in present_declared:
                non_null = int(frame.loc[holdout, name].notna().sum())
                location = f"{name}@{cutoff.isoformat()}" if rolling else name
                window_evidence: dict[str, object] = (
                    {"cutoff": cutoff.isoformat()} if rolling else {}
                )
                if non_null == 0:
                    violations.append(
                        Violation(
                            code="FG-FUTURE-002",
                            severity=Severity.HIGH,
                            message=f"declared future covariate {name!r} has no values in the "
                            "holdout window — it provides no future information",
                            location=location,
                            evidence={
                                **window_evidence,
                                "holdout_rows": int(holdout.sum()),
                                "non_null_in_holdout": 0,
                            },
                        )
                    )
                elif non_null < int(holdout.sum()):
                    missing = frame.loc[holdout & frame[name].isna(), [spec.id_col, spec.time_col]]
                    affected = sorted(str(value) for value in missing[spec.id_col].unique())
                    sample = [
                        {
                            "id": str(row[spec.id_col]),
                            "ds": pd.Timestamp(row[spec.time_col]).isoformat(),
                        }
                        for _, row in missing.head(5).iterrows()
                    ]
                    violations.append(
                        Violation(
                            code="FG-FUTURE-003",
                            severity=Severity.HIGH,
                            message=f"declared future covariate {name!r} has incomplete "
                            "holdout coverage",
                            location=location,
                            evidence={
                                **window_evidence,
                                "holdout_rows": int(holdout.sum()),
                                "non_null_in_holdout": non_null,
                                "missing_holdout_rows": len(missing),
                                "affected_series": affected[:50],
                                "affected_series_count": len(affected),
                                "sample": sample,
                            },
                        )
                    )

        undeclared = [c for c in covariate_cols if c not in set(declared)]
        revision_result = check_revisions(ctx)
        violations.extend(revision_result.violations)

        if violations:
            count = len(violations)
            plural = "s" if count != 1 else ""
            result = CheckResult.failed(
                self.check_id,
                self.name,
                f"{count} future-covariate contract violation{plural}",
                violations,
            )
            result.detail = revision_result.detail
            return result

        if ctx.adapter_error is not None:
            return CheckResult.skipped(
                self.check_id,
                self.name,
                f"adapter introspection failed — {ctx.adapter_error}",
            )

        if revision_result.status is CheckStatus.SKIPPED:
            return revision_result

        return CheckResult.passed(
            self.check_id,
            self.name,
            _pass_summary(present_declared, undeclared, holdout_checked)
            + (f"; {revision_result.summary}" if spec.revisions else ""),
        )


def _holdout_windows(ctx: CheckContext) -> list[tuple[pd.Timestamp, pd.Series]]:
    """Return all comparable validation-window masks.

    Timestamp/cutoff problems are owned by the cutoff check; here we just decline to
    evaluate holdout coverage rather than double-reporting.
    """
    spec = ctx.spec
    required = [spec.time_col]
    if spec.cutoff_col is not None:
        required.append(spec.cutoff_col)
    if any(column not in ctx.frame.columns for column in required):
        return []
    try:
        windows = ctx.windows
        return [
            (
                cutoff,
                holdout_mask(
                    spec,
                    ctx.frame,
                    windows.timestamps,
                    cutoff,
                    expected,
                ),
            )
            for cutoff, expected in windows.origins
        ]
    except (ValueError, TypeError, KeyError):
        return []


def _availability_violations(
    ctx: CheckContext, *, windows: list[tuple[pd.Timestamp, pd.Series]]
) -> list[Violation]:
    """Validate point-in-time covariate availability without inferring it."""
    spec = ctx.spec
    frame = ctx.frame
    violations: list[Violation] = []
    if not spec.availability:
        return violations
    if spec.time_col not in frame.columns or spec.id_col not in frame.columns:
        return violations
    try:
        ds = pd.to_datetime(frame[spec.time_col], errors="raise")
    except (ValueError, TypeError):
        return violations

    for contract in spec.availability:
        column = contract.available_at_col
        if column not in frame.columns:
            violations.append(
                Violation(
                    code="FG-AVAIL-001",
                    severity=Severity.HIGH,
                    message=f"availability timestamp column {column!r} is missing",
                    location=contract.covariate,
                    evidence={"available_at_col": column},
                )
            )
            continue
        try:
            available_at = pd.to_datetime(frame[column], errors="raise")
        except (ValueError, TypeError) as exc:
            violations.append(
                Violation(
                    code="FG-AVAIL-001",
                    severity=Severity.HIGH,
                    message=f"availability timestamp column {column!r} is unparseable",
                    location=contract.covariate,
                    evidence={"available_at_col": column, "error": str(exc)},
                )
            )
            continue

        historical_late = available_at.isna() | available_at.gt(ds)
        if bool(historical_late.any()):
            violations.append(
                _availability_violation(
                    ctx,
                    contract.covariate,
                    column,
                    historical_late,
                    "historical_event",
                    None,
                )
            )
        for cutoff, holdout in windows:
            late = holdout & (available_at.isna() | available_at.gt(cutoff))
            if not bool(late.any()):
                continue
            violations.append(
                _availability_violation(
                    ctx,
                    contract.covariate,
                    column,
                    late,
                    "forecast_origin",
                    cutoff,
                )
            )
    return violations


def _availability_violation(
    ctx: CheckContext,
    covariate: str,
    available_at_col: str,
    affected: pd.Series,
    use_point: str,
    cutoff: pd.Timestamp | None,
) -> Violation:
    spec = ctx.spec
    columns = [spec.id_col, spec.time_col, available_at_col]
    sample = [
        {
            "id": str(row[spec.id_col]),
            "ds": pd.Timestamp(row[spec.time_col]).isoformat(),
            "available_at": (
                None
                if pd.isna(row[available_at_col])
                else pd.Timestamp(row[available_at_col]).isoformat()
            ),
        }
        for _, row in ctx.frame.loc[affected, columns].head(5).iterrows()
    ]
    evidence: dict[str, object] = {
        "covariate": covariate,
        "available_at_col": available_at_col,
        "use_point": use_point,
        "affected_rows": int(affected.sum()),
        "sample": sample,
    }
    location = covariate
    if cutoff is not None:
        evidence["cutoff"] = cutoff.isoformat()
        location = f"{covariate}@{cutoff.isoformat()}"
    return Violation(
        code="FG-AVAIL-002",
        severity=Severity.CRITICAL,
        message=f"covariate {covariate!r} was not available at its {use_point}",
        location=location,
        evidence=evidence,
    )


def _pass_summary(present_declared: list[str], undeclared: list[str], holdout_checked: bool) -> str:
    parts: list[str] = []
    parts.append(
        f"{len(present_declared)} future covariate(s) validated"
        if present_declared
        else "no future covariates declared"
    )
    if undeclared:
        shown = ", ".join(str(c) for c in undeclared[:5])
        more = f" (+{len(undeclared) - 5} more)" if len(undeclared) > 5 else ""
        parts.append(f"{len(undeclared)} covariate column(s) treated as past-only: {shown}{more}")
    if not holdout_checked:
        parts.append("no holdout rows to verify future coverage")
    return "; ".join(parts)
