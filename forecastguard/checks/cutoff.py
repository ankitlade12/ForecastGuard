"""Check 1 — Cutoff integrity (deterministic dataframe validation).

Validates that the dataset is correctly shaped for a single-cutoff, horizon-step
holdout backtest at ``spec.cutoff`` — with zero false positives. It runs purely
on the dataframe; no model or feature function is required.

Semantics (see DECISIONS D-011):

* **Train** rows of a series are those with ``ds <= cutoff``; **holdout** rows
  are those with ``ds > cutoff``.
* A well-formed series has training history and a holdout equal to exactly the
  ``horizon`` grid points (at ``spec.freq``) immediately following the cutoff —
  i.e. ``{cutoff + 1·Δ, …, cutoff + horizon·Δ}``. Anchoring on the cutoff (not on
  the last training row) means a gap *before* the cutoff is not flagged, and an
  on-grid cutoff that sits after the last training row is handled correctly.

Violations:

* ``FG-CUTOFF-001`` — duplicate ``(id, ds)`` rows (CRITICAL)
* ``FG-CUTOFF-002`` — series has no training history; all rows ``> cutoff`` (HIGH)
* ``FG-CUTOFF-003`` — series has an empty holdout; all rows ``<= cutoff`` (HIGH)
* ``FG-CUTOFF-004`` — holdout doesn't match the ``horizon`` grid points after the
  cutoff: too few / too many points, a gap, or off-grid timestamps (HIGH)
* ``FG-CUTOFF-010/011/012/013`` — structural guards: missing column, unparseable
  timestamps, invalid ``freq``/``cutoff``, empty dataset
"""

from __future__ import annotations

import pandas as pd
from pandas.tseries.frequencies import to_offset

from forecastguard.checks.protocol import CheckContext
from forecastguard.models.report import CheckResult, Severity, Violation

# Cap per-series violations so a globally-misconfigured cutoff doesn't print
# thousands of lines; the overflow is summarised in one INFO violation.
_MAX_SERIES_VIOLATIONS = 50


class CutoffIntegrityCheck:
    """Deterministic validation of the train/holdout split. See module docstring."""

    check_id = "cutoff_integrity"
    name = "Cutoff integrity"

    def run(self, ctx: CheckContext) -> CheckResult:
        spec = ctx.spec

        guard = _structural_guard(ctx)
        if guard is not None:
            return CheckResult.failed(self.check_id, self.name, guard.message, [guard])

        cutoff = pd.Timestamp(spec.cutoff)
        offset = to_offset(spec.freq)
        work = ctx.frame[[spec.id_col, spec.time_col]].copy()
        work["_ds"] = pd.to_datetime(work[spec.time_col])

        violations: list[Violation] = []
        dup = _duplicate_violation(work, spec.id_col)
        if dup is not None:
            violations.append(dup)
        violations.extend(_series_violations(work, spec.id_col, cutoff, offset, spec.horizon))

        if violations:
            count = sum(1 for v in violations if v.severity is not Severity.INFO)
            plural = "s" if count != 1 else ""
            return CheckResult.failed(
                self.check_id,
                self.name,
                f"{count} cutoff-integrity violation{plural} at cutoff {cutoff.isoformat()}",
                violations,
            )

        n_series = int(work[spec.id_col].nunique())
        return CheckResult.passed(
            self.check_id,
            self.name,
            f"{n_series} series; holdouts well-formed at cutoff {cutoff.isoformat()} "
            f"(horizon {spec.horizon}, freq {spec.freq})",
        )


def _structural_guard(ctx: CheckContext) -> Violation | None:
    """Return the first blocking structural problem, or None if the frame is sane."""
    spec = ctx.spec
    frame = ctx.frame

    for col in (spec.id_col, spec.time_col):
        if col not in frame.columns:
            return Violation(
                code="FG-CUTOFF-010",
                severity=Severity.CRITICAL,
                message=f"required column {col!r} is missing from the dataset",
                evidence={"columns": [str(c) for c in frame.columns]},
            )

    if len(frame) == 0:
        return Violation(
            code="FG-CUTOFF-013",
            severity=Severity.HIGH,
            message="dataset has no rows",
        )

    try:
        parsed = pd.to_datetime(frame[spec.time_col], errors="raise")
    except (ValueError, TypeError) as exc:
        return Violation(
            code="FG-CUTOFF-011",
            severity=Severity.CRITICAL,
            message=f"column {spec.time_col!r} has timestamps that can't be parsed",
            evidence={"error": str(exc)},
        )
    if bool(parsed.isna().any()):
        return Violation(
            code="FG-CUTOFF-011",
            severity=Severity.CRITICAL,
            message=f"column {spec.time_col!r} contains unparseable/empty timestamps",
            evidence={"na_count": int(parsed.isna().sum())},
        )

    try:
        pd.Timestamp(spec.cutoff)
        to_offset(spec.freq)
    except (ValueError, TypeError) as exc:
        return Violation(
            code="FG-CUTOFF-012",
            severity=Severity.CRITICAL,
            message=f"invalid cutoff {spec.cutoff!r} or freq {spec.freq!r}",
            evidence={"error": str(exc)},
        )
    return None


def _duplicate_violation(work: pd.DataFrame, id_col: str) -> Violation | None:
    """Flag duplicate ``(id, ds)`` pairs — they corrupt both train and holdout."""
    dup_mask = work.duplicated(subset=[id_col, "_ds"], keep=False)
    if not bool(dup_mask.any()):
        return None
    dups = work.loc[dup_mask, [id_col, "_ds"]].drop_duplicates()
    sample = [
        {"id": str(row[id_col]), "ds": pd.Timestamp(row["_ds"]).isoformat()}
        for _, row in dups.head(_MAX_SERIES_VIOLATIONS).iterrows()
    ]
    return Violation(
        code="FG-CUTOFF-001",
        severity=Severity.CRITICAL,
        message=f"{len(dups)} duplicate (id, ds) timestamp(s) — corrupts train and holdout",
        evidence={"duplicate_keys": len(dups), "sample": sample},
    )


def _series_violations(
    work: pd.DataFrame,
    id_col: str,
    cutoff: pd.Timestamp,
    offset: pd.offsets.BaseOffset,
    horizon: int,
) -> list[Violation]:
    """One violation (at most) per malformed series, in deterministic id order."""
    violations: list[Violation] = []
    truncated = 0
    for series_id, group in work.sort_values([id_col, "_ds"]).groupby(id_col, sort=True):
        violation = _classify_series(series_id, group["_ds"], cutoff, offset, horizon)
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
                message=f"and {truncated} more series with holdout issues (output truncated)",
                evidence={"truncated_series": truncated},
            )
        )
    return violations


def _classify_series(
    series_id: object,
    ds: pd.Series,
    cutoff: pd.Timestamp,
    offset: pd.offsets.BaseOffset,
    horizon: int,
) -> Violation | None:
    """Return the single most relevant violation for one series, or None if clean."""
    train = ds[ds <= cutoff]
    holdout = ds[ds > cutoff]

    if train.empty:
        return _series_violation(
            "FG-CUTOFF-002",
            Severity.HIGH,
            series_id,
            f"series {series_id!r} has no training rows at/before the cutoff",
            {"min_ds": pd.Timestamp(ds.min()).isoformat()},
        )
    if holdout.empty:
        return _series_violation(
            "FG-CUTOFF-003",
            Severity.HIGH,
            series_id,
            f"series {series_id!r} has no holdout rows after the cutoff "
            f"(all rows are on/before {cutoff.isoformat()})",
            {"max_ds": pd.Timestamp(ds.max()).isoformat()},
        )

    expected = _grid(cutoff, offset, horizon)
    actual = [pd.Timestamp(x) for x in sorted(holdout.unique())]
    if actual != expected:
        return _holdout_mismatch(series_id, expected, actual, horizon)
    return None


def _grid(anchor: pd.Timestamp, offset: pd.offsets.BaseOffset, horizon: int) -> list[pd.Timestamp]:
    """The ``horizon`` grid points strictly after ``anchor``: anchor+1·Δ … anchor+horizon·Δ."""
    out: list[pd.Timestamp] = []
    cur = anchor
    for _ in range(horizon):
        cur = cur + offset
        out.append(pd.Timestamp(cur))
    return out


def _holdout_mismatch(
    series_id: object,
    expected: list[pd.Timestamp],
    actual: list[pd.Timestamp],
    horizon: int,
) -> Violation:
    """Describe how a series' holdout deviates from the expected horizon window."""
    missing = sorted(set(expected) - set(actual))
    unexpected = sorted(set(actual) - set(expected))
    if len(actual) < horizon:
        reason = "too_few"
    elif len(actual) > horizon:
        reason = "too_many"
    else:
        reason = "misaligned"  # right count, wrong timestamps (gap / off-grid)
    return _series_violation(
        "FG-CUTOFF-004",
        Severity.HIGH,
        series_id,
        f"series {series_id!r} holdout does not match {horizon} step(s) after the cutoff "
        f"({reason})",
        {
            "reason": reason,
            "expected": [t.isoformat() for t in expected],
            "actual": [t.isoformat() for t in actual],
            "missing": [t.isoformat() for t in missing],
            "unexpected": [t.isoformat() for t in unexpected],
        },
    )


def _series_violation(
    code: str,
    severity: Severity,
    series_id: object,
    message: str,
    evidence: dict[str, object],
) -> Violation:
    return Violation(
        code=code,
        severity=severity,
        message=message,
        location=str(series_id),
        evidence=evidence,
    )
