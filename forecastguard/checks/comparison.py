"""Shared comparison and aggregation rules for behavioural probes."""

from collections.abc import Sequence

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype

from forecastguard.models.report import CheckResult, CheckStatus


def aggregate(results: Sequence[CheckResult], summary: str) -> CheckResult:
    violations = [item for result in results for item in result.violations]
    details = [result.detail for result in results if result.detail]
    if violations:
        status = CheckStatus.FAIL
    elif any(result.status is CheckStatus.ERROR for result in results):
        status = CheckStatus.ERROR
    elif not results or any(result.status is CheckStatus.SKIPPED for result in results):
        status = CheckStatus.SKIPPED
    else:
        status = CheckStatus.PASS
    return CheckResult(
        check_id="runtime_leakage",
        name="Runtime leakage",
        status=status,
        summary=summary,
        violations=violations,
        detail="; ".join(details) or None,
    )


def indexed_output(out: object, id_col: str, time_col: str) -> pd.DataFrame | None:
    if not isinstance(out, pd.DataFrame) or out.empty or out.columns.has_duplicates:
        return None
    if id_col not in out or time_col not in out or out[id_col].isna().any():
        return None
    columns = [column for column in out.columns if column not in (id_col, time_col)]
    if not columns:
        return None
    ds = pd.to_datetime(out[time_col], errors="coerce")
    if ds.isna().any():
        return None
    indexed = out[columns].copy()
    indexed.index = pd.MultiIndex.from_arrays([out[id_col], ds], names=[id_col, time_col])
    if indexed.index.has_duplicates:
        return None
    return indexed.sort_index()


def same_shape(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    return left.index.equals(right.index) and set(left.columns) == set(right.columns)


def changed_columns(
    baseline: pd.DataFrame,
    candidate: pd.DataFrame,
    *,
    count_key: str = "changed_pre_cutoff_rows",
    baseline_key: str = "full",
    candidate_key: str = "masked",
) -> dict[str, dict[str, object]]:
    if not same_shape(baseline, candidate):
        raise ValueError("comparison requires aligned rows and columns")
    changed: dict[str, dict[str, object]] = {}
    for column in baseline.columns:
        left, right = baseline[column], candidate[column]
        if is_numeric_dtype(left) and is_numeric_dtype(right):
            mask = ~np.isclose(
                left.to_numpy(dtype=float, na_value=np.nan),
                right.to_numpy(dtype=float, na_value=np.nan),
                rtol=1e-5,
                atol=1e-8,
                equal_nan=True,
            )
        else:
            if isinstance(left.dtype, pd.CategoricalDtype) or isinstance(
                right.dtype, pd.CategoricalDtype
            ):
                left, right = left.astype(object), right.astype(object)
            equal = left.eq(right).fillna(False) | (left.isna() & right.isna())
            mask = ~equal.to_numpy(dtype=bool)
        positions = np.flatnonzero(mask)
        if not len(positions):
            continue
        changed[str(column)] = {
            count_key: len(positions),
            "sample": [
                {
                    "id": str(left.index[position][0]),
                    "ds": pd.Timestamp(left.index[position][1]).isoformat(),
                    baseline_key: _scalar(left.iloc[position]),
                    candidate_key: _scalar(right.iloc[position]),
                }
                for position in positions[:5]
            ],
        }
    return changed


def _scalar(value: object) -> object:
    if pd.isna(value):
        return None
    item = getattr(value, "item", None)
    if callable(item):
        return item()
    return value if isinstance(value, int | float | str | bool) else str(value)
