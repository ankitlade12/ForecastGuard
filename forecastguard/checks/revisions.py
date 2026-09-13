"""Validate supplied input values against publication-time revision histories."""

import numpy as np
import pandas as pd

from forecastguard.checks.protocol import CheckContext
from forecastguard.models.report import CheckResult, Severity, Violation


def check_revisions(ctx: CheckContext) -> CheckResult:
    """Require the latest version published by each origin; never rewrite inputs."""
    spec = ctx.spec
    check_id, name = "known_future_covariates", "Known-future covariates"
    violations: list[Violation] = []
    incomplete = (
        [f"revision history unavailable: {ctx.revision_error}"] if ctx.revision_error else []
    )
    comparisons = 0
    for contract in spec.revisions:
        column = contract.column
        history = ctx.revision_frames.get(column)
        keys = [spec.id_col, spec.time_col]
        required = [*keys, contract.value_col, contract.available_at_col]
        try:
            if history is None:
                incomplete.append(f"revision history for {column!r} was not loaded")
                continue
            if column not in ctx.frame or any(key not in ctx.frame for key in keys):
                raise ValueError("input is missing the revision column or identity/time keys")
            if any(key not in history for key in required):
                raise ValueError("revision history is missing required columns")
            versions = history[required].copy()
            versions[spec.time_col] = pd.to_datetime(versions[spec.time_col], errors="raise")
            versions[contract.available_at_col] = pd.to_datetime(
                versions[contract.available_at_col], errors="raise"
            )
            if versions.isna().any().any():
                raise ValueError(
                    "revision histories require non-null keys, values and publication timestamps"
                )
            if versions.duplicated([*keys, contract.available_at_col]).any():
                raise ValueError("multiple versions share the same id/time/publication timestamp")
            windows = ctx.windows
            audited = 0
            for cutoff, expected in windows.origins:
                if spec.cutoff_col:
                    mask = pd.to_datetime(ctx.frame[spec.cutoff_col]).eq(cutoff) & (
                        column in spec.future_covariates
                    )
                else:
                    mask = windows.timestamps.le(cutoff)
                    if column in spec.future_covariates:
                        mask |= windows.timestamps.isin(expected)
                supplied = ctx.frame.loc[mask, [*keys, column]].copy()
                if supplied.empty:
                    continue
                supplied[spec.time_col] = pd.to_datetime(supplied[spec.time_col])
                supplied = supplied.set_index(keys)[column]
                eligible = versions.loc[versions[contract.available_at_col].le(cutoff)]
                latest = (
                    eligible.sort_values(contract.available_at_col)
                    .drop_duplicates(keys, keep="last")
                    .set_index(keys)
                )
                available = supplied.index.isin(latest.index)
                for code, selected, explanation in [
                    ("FG-REV-002", ~available, "no version was published by the forecast origin"),
                    ("FG-REV-003", available, "input differs from its latest available revision"),
                ]:
                    actual = supplied.loc[selected]
                    reference = latest[contract.value_col].reindex(actual.index)
                    if code == "FG-REV-003":
                        if pd.api.types.is_numeric_dtype(actual) and pd.api.types.is_numeric_dtype(
                            reference
                        ):
                            different = ~np.isclose(
                                actual.to_numpy(dtype=float, na_value=np.nan),
                                reference.to_numpy(dtype=float, na_value=np.nan),
                                rtol=1e-5,
                                atol=1e-8,
                                equal_nan=True,
                            )
                        else:
                            different = ~(
                                actual.eq(reference).fillna(False)
                                | (actual.isna() & reference.isna())
                            )
                        actual, reference = actual.loc[different], reference.loc[different]
                    if not actual.empty:
                        violations.append(
                            Violation(
                                code=code,
                                severity=Severity.CRITICAL,
                                message=f"{column!r}: {explanation}",
                                location=f"{column}@{cutoff.isoformat()}",
                                evidence={
                                    "column": column,
                                    "cutoff": cutoff.isoformat(),
                                    "affected_rows": len(actual),
                                    "policy": contract.policy,
                                    "sample": [
                                        {
                                            "id": str(index[0]),
                                            "ds": pd.Timestamp(index[1]).isoformat(),
                                            "actual": _value(actual.loc[index]),
                                            "expected": _value(reference.loc[index]),
                                        }
                                        for index in actual.index[:5]
                                    ],
                                },
                            )
                        )
                audited += len(supplied)
            comparisons += audited
            if not audited:
                incomplete.append(
                    f"no auditable input rows for revision column {column!r}; scoring targets are excluded"
                )
        except (ValueError, TypeError, KeyError) as exc:
            violations.append(
                Violation(
                    code="FG-REV-001",
                    severity=Severity.HIGH,
                    message=f"invalid revision contract for {column!r}: {exc}",
                    location=column,
                    evidence={"column": column},
                )
            )
    if violations:
        result = CheckResult.failed(
            check_id, name, f"{len(violations)} revision violation(s)", violations
        )
        result.detail = "; ".join(incomplete) or None
        return result
    if incomplete:
        return CheckResult.skipped(check_id, name, "; ".join(incomplete))
    return CheckResult.passed(check_id, name, f"{comparisons} revision value/origin comparisons")


def _value(value: object) -> object:
    if pd.isna(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value if isinstance(value, str | int | float | bool) else str(value)
