"""Load a :class:`ForecastSpec` from a YAML config file (``forecastguard.yaml``)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from forecastguard.models.spec import ForecastSpec


def load_spec(path: str | Path) -> ForecastSpec:
    """Parse a YAML spec file into a validated :class:`ForecastSpec`.

    A relative ``data`` path is resolved against the spec file's own directory
    so a spec is runnable from any working directory.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"spec file not found: {path}")
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"spec file {path} must contain a top-level mapping")
    spec = ForecastSpec.model_validate(raw)
    if not spec.data.is_absolute():
        spec = spec.model_copy(update={"data": (path.parent / spec.data).resolve()})
    if (
        spec.adapter is not None
        and spec.adapter.model_path is not None
        and not spec.adapter.model_path.is_absolute()
    ):
        adapter = spec.adapter.model_copy(
            update={"model_path": (path.parent / spec.adapter.model_path).resolve()}
        )
        spec = spec.model_copy(update={"adapter": adapter})
    return spec
