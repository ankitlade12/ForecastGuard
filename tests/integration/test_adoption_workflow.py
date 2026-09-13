"""Executable setup and planning boundaries."""

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml
from click.testing import CliRunner

from forecastguard.cli import app
from forecastguard.config import load_spec
from forecastguard.runner import run_checks
from tests.conftest import REPO_ROOT

pytestmark = pytest.mark.integration


def write_data(tmp_path: Path) -> Path:
    path = tmp_path / "data.csv"
    pd.DataFrame(
        {
            "unique_id": ["A"] * 12,
            "ds": pd.date_range("2024-01-01", periods=12),
            "y": [float(i) for i in range(12)],
        }
    ).to_csv(path, index=False)
    return path


def test_init_plan_and_real_mlforecast_run(tmp_path: Path) -> None:
    pytest.importorskip("mlforecast")
    data = write_data(tmp_path)
    config = tmp_path / "generated.yaml"
    result = CliRunner().invoke(
        app,
        [
            "init",
            "--data",
            str(data),
            "--output",
            str(config),
            "--framework",
            "mlforecast",
            "--horizon",
            "2",
            "--future-covariates",
            "",
            "--static-covariates",
            "",
            "--no-input",
        ],
    )
    assert result.exit_code == 0, result.output
    result = CliRunner().invoke(app, ["plan", "--spec", str(config), "--format", "json"])
    assert result.exit_code == 0, result.output
    plan = json.loads(result.output)
    assert plan["primary_calls"] == 5
    result = CliRunner().invoke(app, ["run", "--spec", str(config), "--strict", "--format", "json"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["runtime_calls"] == 5
    assert len(report["coverage"]) == 3
    assert {row["status"] for row in report["coverage"]} == {"pass"}


def test_init_requires_explicit_availability_and_preserves_files(tmp_path: Path) -> None:
    data = write_data(tmp_path)
    output = tmp_path / "existing.yaml"
    output.write_text("keep me")
    result = CliRunner().invoke(
        app, ["init", "--data", str(data), "--output", str(output), "--horizon", "2", "--no-input"]
    )
    assert result.exit_code != 0
    assert output.read_text() == "keep me"


def test_plan_does_not_import_user_code_and_reports_blocked_budget(tmp_path: Path) -> None:
    data = write_data(tmp_path)
    path = tmp_path / "spec.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "data": str(data),
                "cutoff": "2024-01-10",
                "horizon": 2,
                "freq": "D",
                "forecast_fn": "does_not_exist:predict",
                "max_probe_calls": 0,
            }
        )
    )
    result = CliRunner().invoke(app, ["plan", "--spec", str(path), "--format", "json"])
    assert result.exit_code == 1
    assert json.loads(result.output)["budget_exceeded"] is True
    report = run_checks(load_spec(path))
    assert report.runtime_calls == 0
    assert {row.status for row in report.coverage} == {"skipped"}


def test_ready_plan_leaves_callable_imports_unchecked(tmp_path: Path) -> None:
    data = write_data(tmp_path)
    path = tmp_path / "ready.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "data": str(data),
                "cutoff": "2024-01-10",
                "horizon": 2,
                "freq": "D",
                "pipeline_factory": "does_not_exist:factory",
                "diagnostics": True,
                "max_probe_calls": 5,
            }
        )
    )
    result = CliRunner().invoke(app, ["plan", "--spec", str(path), "--format", "json"])
    assert result.exit_code == 0, result.output
    plan = json.loads(result.output)
    assert plan["primary_calls"] == 3
    assert plan["diagnostic_call_limit"] == 2
    assert plan["maximum_calls"] == 5


def test_init_refuses_wrapper_collision_without_creating_spec(tmp_path: Path) -> None:
    data = write_data(tmp_path)
    wrapper = tmp_path / "example_pipeline.py"
    wrapper.write_text("keep this code")
    path = tmp_path / "example.yaml"
    result = CliRunner().invoke(
        app,
        [
            "init",
            "--data",
            str(data),
            "--output",
            str(path),
            "--framework",
            "mlforecast",
            "--horizon",
            "2",
            "--future-covariates",
            "",
            "--static-covariates",
            "",
            "--no-input",
        ],
    )
    assert result.exit_code == 1
    assert not path.exists()
    assert wrapper.read_text() == "keep this code"


def test_relative_revision_paths_and_invalid_history_block_imports(tmp_path: Path) -> None:
    data = write_data(tmp_path)
    path = tmp_path / "revisions.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "data": str(data),
                "cutoff": "2024-01-10",
                "horizon": 2,
                "freq": "D",
                "forecast_fn": "does_not_exist:predict",
                "revisions": [{"column": "y", "data": "missing.csv"}],
            }
        )
    )
    spec = load_spec(path)
    assert spec.revisions[0].data == tmp_path / "missing.csv"
    report = run_checks(spec)
    assert report.runtime_calls == 0
    assert report.exit_code(strict=True) == 1
    assert report.results[1].status.value == "skipped"


def test_origin_selection_and_diagnostics_are_in_all_reports(tmp_path: Path) -> None:
    data = write_data(tmp_path)
    path = tmp_path / "origins.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "data": str(data),
                "cutoffs": ["2024-01-08", "2024-01-10"],
                "horizon": 2,
                "freq": "D",
                "forecast_fn": "examples.nixtla_rolling.mlforecast_tutorial:leaky_forecast",
            }
        )
    )
    # Use an importable local feature fixture to avoid optional model dependencies.
    spec = yaml.safe_load(path.read_text())
    spec.pop("forecast_fn")
    spec["feature_fn"] = "examples.runtime_leakage.features:leaky_features"
    path.write_text(yaml.safe_dump(spec))
    sarif = tmp_path / "report.sarif"
    result = CliRunner().invoke(
        app,
        [
            "run",
            "--spec",
            str(path),
            "--origin",
            "2024-01-10",
            "--diagnose",
            "--format",
            "json",
            "--sarif-output",
            str(sarif),
        ],
    )
    assert result.exit_code == 1, result.output
    report = json.loads(result.output)
    assert {c["cutoff"] for c in report["coverage"]} == {"2024-01-10T00:00:00"}
    assert report["diagnostics"]
    assert "--origin" in report["rerun_command"]
    properties = json.loads(sarif.read_text())["runs"][0]["properties"]
    assert properties["coverage"] == report["coverage"]
    assert properties["diagnostics"] == report["diagnostics"]


@pytest.mark.parametrize(
    ("name", "extra", "exit_code"),
    [
        ("replay-clean.yaml", [], 0),
        ("replay-leaky.yaml", [], 1),
        ("diagnostics.yaml", ["--diagnose"], 1),
        ("revisions.yaml", ["--origin", "2024-01-04"], 0),
        ("revisions.yaml", [], 1),
    ],
)
def test_adoption_examples(name: str, extra: list[str], exit_code: int) -> None:
    result = CliRunner().invoke(
        app,
        [
            "run",
            "--spec",
            str(REPO_ROOT / "examples/adoption" / name),
            "--strict",
            "--format",
            "json",
            *extra,
        ],
    )
    assert result.exit_code == exit_code, result.output
    report = json.loads(result.output)
    assert len(report["results"]) == 3
    if name == "revisions.yaml" and not extra:
        assert any(v["code"] == "FG-REV-003" for c in report["results"] for v in c["violations"])
        assert report["runtime_calls"] == 0


def test_generated_wrapper_supports_custom_columns_and_user_factory(tmp_path: Path) -> None:
    pytest.importorskip("mlforecast")
    data = write_data(tmp_path)
    frame = pd.read_csv(data).rename(columns={"unique_id": "item", "ds": "when", "y": "demand"})
    frame["promo"] = [0, 1] * 6
    frame.to_csv(data, index=False)
    (tmp_path / "custom_adoption_model.py").write_text(
        "from mlforecast import MLForecast\nfrom sklearn.linear_model import LinearRegression\n"
        "def create():\n    return MLForecast(models=LinearRegression(), freq='D', lags=[1, 2])\n"
    )
    path = tmp_path / "custom.yaml"
    result = CliRunner().invoke(
        app,
        [
            "init",
            "--data",
            str(data),
            "--output",
            str(path),
            "--framework",
            "mlforecast",
            "--model-factory",
            "custom_adoption_model:create",
            "--horizon",
            "2",
            "--id-col",
            "item",
            "--time-col",
            "when",
            "--target-col",
            "demand",
            "--future-covariates",
            "promo",
            "--static-covariates",
            "",
            "--no-input",
        ],
    )
    assert result.exit_code == 0, result.output
    result = CliRunner().invoke(app, ["run", "--spec", str(path), "--strict"])
    assert result.exit_code == 0, result.output


def test_interactive_init_confirms_roles_and_never_guesses_availability(tmp_path: Path) -> None:
    data = write_data(tmp_path)
    frame = pd.read_csv(data)
    frame["future_promo"] = 1
    frame.to_csv(data, index=False)
    output = tmp_path / "interactive.yaml"
    result = CliRunner().invoke(
        app,
        [
            "init",
            "--data",
            str(data),
            "--output",
            str(output),
            "--id-col",
            "unique_id",
            "--time-col",
            "ds",
            "--target-col",
            "y",
            "--horizon",
            "2",
            "--freq",
            "D",
            "--cutoff",
            "2024-01-10",
        ],
        input="\n\n",
    )
    assert result.exit_code == 0, result.output
    assert load_spec(output).future_covariates == []
    assert "actually known" in result.output
