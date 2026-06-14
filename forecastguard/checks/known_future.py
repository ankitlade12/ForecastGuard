"""Check 2 — Known-future covariates (declared-vs-used contract diff).

A covariate consumed at predict time that won't exist in production is leakage in
disguise. The user *declares* which covariates are known-at-predict-time via
``spec.future_covariates``; this check diffs that declaration against the data.

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

Undeclared covariate columns are reported in the PASS summary as "past-only", not
as failures.
"""

from __future__ import annotations

import pandas as pd

from forecastguard.checks.protocol import CheckContext
from forecastguard.models.report import CheckResult, Severity, Violation


class KnownFutureCovariatesCheck:
    """Validates the declared future-covariate contract against the data."""

    check_id = "known_future_covariates"
    name = "Known-future covariates"

    def run(self, ctx: CheckContext) -> CheckResult:
        spec = ctx.spec
        frame = ctx.frame
        column_set = set(frame.columns)

        reserved = {spec.id_col, spec.time_col, spec.target_col, *spec.static_covariates}
        covariate_cols = [c for c in frame.columns if c not in reserved]
        declared = list(dict.fromkeys(spec.future_covariates))  # dedupe, keep order

        violations: list[Violation] = []

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

        # FG-FUTURE-002 — declared future covariate is absent across the holdout.
        present_declared = [d for d in declared if d in column_set]
        holdout = _holdout_mask(ctx)
        holdout_checked = False
        if holdout is not None and bool(holdout.any()):
            holdout_checked = True
            for name in present_declared:
                non_null = int(frame.loc[holdout, name].notna().sum())
                if non_null == 0:
                    violations.append(
                        Violation(
                            code="FG-FUTURE-002",
                            severity=Severity.HIGH,
                            message=f"declared future covariate {name!r} has no values in the "
                            "holdout window — it provides no future information",
                            location=name,
                            evidence={"holdout_rows": int(holdout.sum()), "non_null_in_holdout": 0},
                        )
                    )

        undeclared = [c for c in covariate_cols if c not in set(declared)]

        if violations:
            count = len(violations)
            plural = "s" if count != 1 else ""
            return CheckResult.failed(
                self.check_id,
                self.name,
                f"{count} future-covariate contract violation{plural}",
                violations,
            )

        return CheckResult.passed(
            self.check_id,
            self.name,
            _pass_summary(present_declared, undeclared, holdout_checked),
        )


def _holdout_mask(ctx: CheckContext) -> pd.Series | None:
    """Boolean mask of holdout rows (``ds > cutoff``), or None if time can't be read.

    Timestamp/cutoff problems are owned by the cutoff check; here we just decline to
    evaluate holdout coverage rather than double-reporting.
    """
    spec = ctx.spec
    if spec.time_col not in ctx.frame.columns:
        return None
    try:
        ds = pd.to_datetime(ctx.frame[spec.time_col], errors="raise")
        cutoff = pd.Timestamp(spec.cutoff)
    except (ValueError, TypeError):
        return None
    return ds > cutoff


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
