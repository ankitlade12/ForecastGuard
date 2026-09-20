"""Unit tests for spec loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from forecastguard.config import load_spec

pytestmark = pytest.mark.unit


def test_yaml_still_requires_data(tmp_path: Path) -> None:
    path = tmp_path / "forecastguard.yaml"
    path.write_text("cutoff: '2024-01-01'\nhorizon: 1\nfreq: D\n")
    with pytest.raises(ValueError, match="YAML specs require data"):
        load_spec(path)


def test_load_spec_resolves_relative_data_path(tmp_path: Path) -> None:
    (tmp_path / "data.csv").write_text("unique_id,ds,y\nA,2024-01-01,1\n", encoding="utf-8")
    (tmp_path / "forecastguard.yaml").write_text(
        'name: t\ndata: data.csv\ncutoff: "2024-01-01"\nhorizon: 7\nfreq: D\n',
        encoding="utf-8",
    )
    spec = load_spec(tmp_path / "forecastguard.yaml")
    assert spec.name == "t"
    assert spec.data is not None and spec.data.is_absolute()
    assert spec.data == (tmp_path / "data.csv").resolve()


def test_load_spec_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_spec(tmp_path / "nope.yaml")


def test_load_spec_rejects_non_mapping(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="top-level mapping"):
        load_spec(bad)


def test_load_spec_resolves_relative_adapter_model_path(tmp_path: Path) -> None:
    (tmp_path / "data.csv").write_text("unique_id,ds,y\nA,2024-01-01,1\n", encoding="utf-8")
    config = tmp_path / "forecastguard.yaml"
    config.write_text(
        "\n".join(
            [
                "data: data.csv",
                'cutoff: "2024-01-01"',
                "horizon: 1",
                "freq: D",
                "adapter:",
                "  kind: mlforecast",
                "  model_path: fitted-model",
            ]
        ),
        encoding="utf-8",
    )
    spec = load_spec(config)
    assert spec.adapter is not None
    assert spec.adapter.model_path == (tmp_path / "fitted-model").resolve()
