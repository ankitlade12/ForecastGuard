"""Integration tests: the runner + CLI run end to end on the quickstart example."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from forecastguard.cli import app
from forecastguard.config import load_spec
from forecastguard.models.report import Report
from forecastguard.runner import run_checks
from tests.conftest import QUICKSTART_SPEC, REPO_ROOT

pytestmark = pytest.mark.integration


def test_run_checks_on_quickstart() -> None:
    report = run_checks(load_spec(QUICKSTART_SPEC))
    assert len(report.results) == 3
    assert not report.failed
    assert report.has_skips


def test_cli_run_quickstart_passes() -> None:
    result = CliRunner().invoke(app, ["run", "--spec", str(QUICKSTART_SPEC)])
    assert result.exit_code == 0, result.output
    assert "ForecastGuard CI" in result.output
    assert "SKIP" in result.output


def test_cli_strict_promotes_skips_to_failure() -> None:
    result = CliRunner().invoke(app, ["run", "--spec", str(QUICKSTART_SPEC), "--strict"])
    assert result.exit_code == 1
    assert "FAIL" in result.output


def test_cli_json_output_is_a_versioned_report() -> None:
    result = CliRunner().invoke(app, ["run", "--spec", str(QUICKSTART_SPEC), "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema_version"] == "1.0"
    assert Report.model_validate(payload).has_skips
    assert "ForecastGuard CI" not in result.output


def test_cli_json_preserves_strict_exit_semantics() -> None:
    result = CliRunner().invoke(
        app,
        ["run", "--spec", str(QUICKSTART_SPEC), "--format", "json", "--strict"],
    )
    assert result.exit_code == 1
    assert Report.model_validate_json(result.output).has_skips


def test_cli_missing_spec_errors_cleanly() -> None:
    result = CliRunner().invoke(app, ["run", "--spec", "does_not_exist.yaml"])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_cli_writes_json_sarif_and_github_summary(tmp_path: Path) -> None:
    json_path = tmp_path / "report.json"
    sarif_path = tmp_path / "report.sarif"
    summary_path = tmp_path / "summary.md"
    result = CliRunner().invoke(
        app,
        [
            "run",
            "--spec",
            str(QUICKSTART_SPEC),
            "--json-output",
            str(json_path),
            "--sarif-output",
            str(sarif_path),
            "--github",
        ],
        env={"GITHUB_STEP_SUMMARY": str(summary_path)},
    )
    assert result.exit_code == 0, result.output
    assert '"schema_version": "1.0"' in json_path.read_text()
    assert '"version": "2.1.0"' in sarif_path.read_text()
    assert "ForecastGuard" in summary_path.read_text()


@pytest.mark.parametrize(
    ("spec_path", "expected_exit", "snippets"),
    [
        (
            "examples/cutoff_integrity/clean/forecastguard.yaml",
            0,
            ["[PASS] Cutoff integrity"],
        ),
        (
            "examples/cutoff_integrity/broken/forecastguard.yaml",
            1,
            ["FG-CUTOFF-001", "FG-CUTOFF-004", "FG-CUTOFF-003"],
        ),
        (
            "examples/known_future/clean/forecastguard.yaml",
            0,
            ["[PASS] Known-future covariates"],
        ),
        (
            "examples/known_future/broken/forecastguard.yaml",
            1,
            ["FG-FUTURE-001", "FG-FUTURE-002"],
        ),
        (
            "examples/runtime_leakage/clean.yaml",
            0,
            ["[PASS] Runtime leakage"],
        ),
        (
            "examples/runtime_leakage/leaky.yaml",
            1,
            ["FG-LEAK-001", "centered_mean_3", "y_vs_series_mean"],
        ),
        (
            "examples/nixtla_rolling/raw.yaml",
            0,
            ["nixtla-rolling-raw-history", "[PASS] Cutoff integrity"],
        ),
        (
            "examples/nixtla_rolling/cv.yaml",
            0,
            ["nixtla-cross-validation-output", "[PASS] Cutoff integrity"],
        ),
    ],
)
def test_cli_advertised_examples(spec_path: str, expected_exit: int, snippets: list[str]) -> None:
    result = CliRunner().invoke(app, ["run", "--spec", str(REPO_ROOT / spec_path)])
    assert result.exit_code == expected_exit, result.output
    for snippet in snippets:
        assert snippet in result.output
