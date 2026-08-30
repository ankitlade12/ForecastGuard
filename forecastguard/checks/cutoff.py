"""Check 1 — cutoff integrity for single and rolling-origin backtests.

The check accepts a raw train-plus-validation panel with either one ``cutoff``
or several ``cutoffs``, plus Nixtla-style cross-validation output identified by
``cutoff_col``. Rolling windows are always bounded to the declared horizon.

Violations:

* ``FG-CUTOFF-001`` — duplicate validation key (CRITICAL)
* ``FG-CUTOFF-002`` — raw-history series has no training history (HIGH)
* ``FG-CUTOFF-003`` — series/window has an empty holdout (HIGH)
* ``FG-CUTOFF-004`` — holdout differs from the expected horizon grid (HIGH)
* ``FG-CUTOFF-010/011/012/013`` — structural guards
* ``FG-CUTOFF-014`` — null series identifier (CRITICAL)
"""

from __future__ import annotations

import pandas as pd
from pandas.tseries.frequencies import to_offset

from forecastguard.checks.protocol import CheckContext
from forecastguard.models.report import CheckResult, Severity, Violation
from forecastguard.windows import forecast_grid, holdout_mask, window_cutoffs, window_location

_MAX_SERIES_VIOLATIONS = 50


class CutoffIntegrityCheck:
    """Deterministic validation of all declared train/holdout windows."""

    check_id = "cutoff_integrity"
    name = "Cutoff integrity"

    def run(self, ctx: CheckContext) -> CheckResult:
        spec = ctx.spec
        guard = _structural_guard(ctx)
        if guard is not None:
            return CheckResult.failed(self.check_id, self.name, guard.message, [guard])

        offset = to_offset(spec.freq)
        columns = [spec.id_col, spec.time_col]
        if spec.cutoff_col is not None:
            columns.append(spec.cutoff_col)
        work = ctx.frame[columns].copy()
        work["_ds"] = pd.to_datetime(work[spec.time_col])
        if spec.cutoff_col is not None:
            work["_cutoff"] = pd.to_datetime(work[spec.cutoff_col])

        cutoffs = window_cutoffs(spec, work)
        rolling = spec.cutoff_col is not None or bool(spec.cutoffs)
        violations: list[Violation] = []
        duplicate = _duplicate_violation(work, spec.id_col, cv_output=spec.cutoff_col is not None)
        if duplicate is not None:
            violations.append(duplicate)
        violations.extend(
            _window_violations(
                work,
                spec.id_col,
                cutoffs,
                offset,
                spec.horizon,
                ctx,
                rolling=rolling,
            )
        )

        if violations:
            count = sum(1 for violation in violations if violation.severity is not Severity.INFO)
            plural = "s" if count != 1 else ""
            scope = (
                f"across {len(cutoffs)} window(s)"
                if rolling
                else f"at cutoff {cutoffs[0].isoformat()}"
            )
            return CheckResult.failed(
                self.check_id,
                self.name,
                f"{count} cutoff-integrity violation{plural} {scope}",
                violations,
            )

        n_series = int(work[spec.id_col].nunique())
        if rolling:
            return CheckResult.passed(
                self.check_id,
                self.name,
                f"{n_series} series; {len(cutoffs)} window(s) well-formed "
                f"(horizon {spec.horizon}, freq {spec.freq})",
            )
        return CheckResult.passed(
            self.check_id,
            self.name,
            f"{n_series} series; holdouts well-formed at cutoff {cutoffs[0].isoformat()} "
            f"(horizon {spec.horizon}, freq {spec.freq})",
        )


def _structural_guard(ctx: CheckContext) -> Violation | None:
    spec = ctx.spec
    frame = ctx.frame
    required = [spec.id_col, spec.time_col, spec.target_col]
    if spec.cutoff_col is not None:
        required.append(spec.cutoff_col)
    for column in required:
        if column not in frame.columns:
            return Violation(
                code="FG-CUTOFF-010",
                severity=Severity.CRITICAL,
                message=f"required column {column!r} is missing from the dataset",
                evidence={"columns": [str(value) for value in frame.columns]},
            )
    if frame.empty:
        return Violation(
            code="FG-CUTOFF-013", severity=Severity.HIGH, message="dataset has no rows"
        )
    null_ids = frame[spec.id_col].isna()
    if bool(null_ids.any()):
        return Violation(
            code="FG-CUTOFF-014",
            severity=Severity.CRITICAL,
            message=f"column {spec.id_col!r} contains null series identifiers",
            evidence={"null_id_rows": int(null_ids.sum())},
        )
    try:
        parsed_ds = pd.to_datetime(frame[spec.time_col], errors="raise")
        if spec.cutoff_col is not None:
            parsed_cutoffs = pd.to_datetime(frame[spec.cutoff_col], errors="raise")
            if bool(parsed_cutoffs.isna().any()):
                raise ValueError(f"column {spec.cutoff_col!r} contains empty cutoffs")
    except (ValueError, TypeError) as exc:
        return Violation(
            code="FG-CUTOFF-011",
            severity=Severity.CRITICAL,
            message="timestamp or cutoff column has values that can't be parsed",
            evidence={"error": str(exc)},
        )
    if bool(parsed_ds.isna().any()):
        return Violation(
            code="FG-CUTOFF-011",
            severity=Severity.CRITICAL,
            message=f"column {spec.time_col!r} contains unparseable/empty timestamps",
            evidence={"na_count": int(parsed_ds.isna().sum())},
        )
    try:
        window_cutoffs(spec, frame)
        to_offset(spec.freq)
    except (ValueError, TypeError, KeyError) as exc:
        return Violation(
            code="FG-CUTOFF-012",
            severity=Severity.CRITICAL,
            message="invalid cutoff source or frequency",
            evidence={"error": str(exc), "freq": spec.freq},
        )
    return None


def _duplicate_violation(work: pd.DataFrame, id_col: str, *, cv_output: bool) -> Violation | None:
    keys = [id_col, "_cutoff", "_ds"] if cv_output else [id_col, "_ds"]
    duplicate_mask = work.duplicated(subset=keys, keep=False)
    if not bool(duplicate_mask.any()):
        return None
    duplicates = work.loc[duplicate_mask, keys].drop_duplicates()
    sample: list[dict[str, object]] = []
    for _, row in duplicates.head(_MAX_SERIES_VIOLATIONS).iterrows():
        item: dict[str, object] = {
            "id": str(row[id_col]),
            "ds": pd.Timestamp(row["_ds"]).isoformat(),
        }
        if cv_output:
            item["cutoff"] = pd.Timestamp(row["_cutoff"]).isoformat()
        sample.append(item)
    label = "(id, cutoff, ds)" if cv_output else "(id, ds)"
    return Violation(
        code="FG-CUTOFF-001",
        severity=Severity.CRITICAL,
        message=f"{len(duplicates)} duplicate {label} timestamp(s) — corrupts validation",
        evidence={"duplicate_keys": len(duplicates), "sample": sample},
    )


def _window_violations(
    work: pd.DataFrame,
    id_col: str,
    cutoffs: list[pd.Timestamp],
    offset: pd.offsets.BaseOffset,
    horizon: int,
    ctx: CheckContext,
    *,
    rolling: bool,
) -> list[Violation]:
    violations: list[Violation] = []
    truncated = 0
    groups = {
        series_id: group
        for series_id, group in work.sort_values([id_col, "_ds"]).groupby(id_col, sort=False)
    }
    ids = sorted(groups, key=str)
    for cutoff in cutoffs:
        expected = forecast_grid(cutoff, offset, horizon)
        for series_id in ids:
            group = groups[series_id]
            violation = _classify_window(series_id, group, cutoff, expected, ctx, rolling=rolling)
            if violation is None:
                continue
            if len(violations) < _MAX_SERIES_VIOLATIONS:
                violations.append(violation)
            else:
                truncated += 1
    if truncated:
        violations.append(
            Violation(
                code="FG-CUTOFF-099",
                severity=Severity.INFO,
                message=f"and {truncated} more series/window issues (output truncated)",
                evidence={"truncated_windows": truncated},
            )
        )
    return violations


def _classify_window(
    series_id: object,
    group: pd.DataFrame,
    cutoff: pd.Timestamp,
    expected: list[pd.Timestamp],
    ctx: CheckContext,
    *,
    rolling: bool,
) -> Violation | None:
    spec = ctx.spec
    if spec.cutoff_col is None and group.loc[group["_ds"].le(cutoff)].empty:
        return _series_violation(
            "FG-CUTOFF-002",
            series_id,
            cutoff,
            rolling,
            f"series {series_id!r} has no training rows at/before the cutoff",
            {"min_ds": pd.Timestamp(group["_ds"].min()).isoformat()},
        )
    selected = holdout_mask(spec, group, group["_ds"], cutoff, expected)
    actual = [pd.Timestamp(value) for value in sorted(group.loc[selected, "_ds"].unique())]
    if not actual:
        evidence: dict[str, object] = {"cutoff": cutoff.isoformat()}
        if spec.cutoff_col is None:
            evidence["max_ds"] = pd.Timestamp(group["_ds"].max()).isoformat()
        return _series_violation(
            "FG-CUTOFF-003",
            series_id,
            cutoff,
            rolling,
            f"series {series_id!r} has no holdout rows for cutoff {cutoff.isoformat()}",
            evidence,
        )
    if actual != expected:
        return _holdout_mismatch(series_id, cutoff, expected, actual, rolling=rolling)
    return None


def _holdout_mismatch(
    series_id: object,
    cutoff: pd.Timestamp,
    expected: list[pd.Timestamp],
    actual: list[pd.Timestamp],
    *,
    rolling: bool,
) -> Violation:
    missing = sorted(set(expected) - set(actual))
    unexpected = sorted(set(actual) - set(expected))
    if len(actual) < len(expected):
        reason = "too_few"
    elif len(actual) > len(expected):
        reason = "too_many"
    else:
        reason = "misaligned"
    return _series_violation(
        "FG-CUTOFF-004",
        series_id,
        cutoff,
        rolling,
        f"series {series_id!r} holdout does not match {len(expected)} step(s) after the "
        f"cutoff ({reason})",
        {
            "cutoff": cutoff.isoformat(),
            "reason": reason,
            "expected": [value.isoformat() for value in expected],
            "actual": [value.isoformat() for value in actual],
            "missing": [value.isoformat() for value in missing],
            "unexpected": [value.isoformat() for value in unexpected],
        },
    )


def _series_violation(
    code: str,
    series_id: object,
    cutoff: pd.Timestamp,
    rolling: bool,
    message: str,
    evidence: dict[str, object],
) -> Violation:
    if rolling:
        evidence = {**evidence, "cutoff": cutoff.isoformat()}
    return Violation(
        code=code,
        severity=Severity.HIGH,
        message=message,
        location=window_location(series_id, cutoff, rolling=rolling),
        evidence=evidence,
    )
