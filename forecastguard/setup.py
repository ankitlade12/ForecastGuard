"""Typed configuration generation and optional MLForecast integration scaffolds."""

import os
import re
from pathlib import Path

import pandas as pd
import yaml
from pydantic import BaseModel

from forecastguard.checks.cutoff import CutoffIntegrityCheck
from forecastguard.checks.known_future import KnownFutureCovariatesCheck
from forecastguard.checks.protocol import CheckContext
from forecastguard.models.spec import ForecastSpec


class InitResult(BaseModel):
    """Paths and contract produced by a successful initialization."""

    spec_path: Path
    wrapper_path: Path | None
    spec: ForecastSpec


def suggest_column(columns: list[str], candidates: tuple[str, ...]) -> str:
    """Suggest a structural column; availability is never inferred."""
    return next((value for value in candidates if value in columns), columns[0])


def infer_frequency(frame: pd.DataFrame, id_col: str, time_col: str) -> str | None:
    """Suggest a frequency only when each series has the same regular grid."""
    frequencies = set()
    for _, series in frame.groupby(id_col):
        dates = pd.DatetimeIndex(pd.to_datetime(series[time_col])).sort_values().unique()
        if len(dates) < 3:
            return None
        frequencies.add(pd.infer_freq(dates))
    return (
        str(next(iter(frequencies))) if len(frequencies) == 1 and None not in frequencies else None
    )


def initialize(
    spec: ForecastSpec,
    frame: pd.DataFrame,
    output: Path,
    *,
    framework: str,
    model_factory: str | None = None,
) -> InitResult:
    """Validate a generated spec and create new files, never overwrite existing work."""
    if spec.data is None:
        raise ValueError("initialization requires a data path for the generated YAML spec")
    output = output.resolve()
    module = re.sub(r"\W", "_", output.stem) + "_pipeline"
    if not module.isidentifier():
        module = "fg_" + module
    wrapper = output.parent / f"{module}.py" if framework == "mlforecast" else None
    if model_factory and (":" not in model_factory or not all(model_factory.split(":", 1))):
        raise ValueError("model factory must look like package.module:callable")
    if wrapper:
        spec = spec.model_copy(update={"forecast_fn": f"{module}:forecast"})
    ctx = CheckContext(spec=spec, frame=frame)
    for check in (CutoffIntegrityCheck(), KnownFutureCovariatesCheck()):
        result = check.run(ctx)
        if result.status.value != "pass":
            raise ValueError(
                f"cannot initialize: {result.summary}: "
                + "; ".join(v.message for v in result.violations)
            )
    paths = [output] + ([wrapper] if wrapper else [])
    if any(path.exists() for path in paths):
        raise FileExistsError(
            "output spec or generated wrapper already exists; choose a new output path"
        )
    payload = spec.model_dump(mode="json", exclude_none=True)
    assert spec.data is not None
    payload["data"] = os.path.relpath(spec.data.resolve(), output.parent)
    contents = [yaml.safe_dump(payload, sort_keys=False)]
    if wrapper:
        contents.append(_wrapper(spec, model_factory))
    output.parent.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    try:
        for path, content in zip(paths, contents, strict=True):
            with path.open("x", encoding="utf-8") as handle:
                created.append(path)
                handle.write(content)
    except OSError:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return InitResult(spec_path=output, wrapper_path=wrapper, spec=spec)


def _wrapper(spec: ForecastSpec, model_factory: str | None) -> str:
    return f'''"""Generated MLForecast wrapper. Replace the starter model with your model factory.

Fit preprocessing inside the factory/model pipeline. Frozen external artifacts
are outside this callable's validation coverage.
"""
from forecastguard.adapters.mlforecast_runtime import forecast_with_mlforecast
import pandas as pd


def forecast(train: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
    """Refit the selected model on the supplied history and predict the horizon."""
    return forecast_with_mlforecast(
        train, future, model_factory={model_factory!r}, freq={spec.freq!r},
        id_col={spec.id_col!r}, time_col={spec.time_col!r}, target_col={spec.target_col!r},
        future_covariates={spec.future_covariates!r}, static_covariates={spec.static_covariates!r},
    )
'''
