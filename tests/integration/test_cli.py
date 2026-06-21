"""Integration tests: the runner + CLI run end to end on the quickstart example."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from forecastguard.cli import app
from forecastguard.config import load_spec
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


def test_cli_missing_spec_errors_cleanly() -> None:
    result = CliRunner().invoke(app, ["run", "--spec", "does_not_exist.yaml"])
    assert result.exit_code != 0
    assert "not found" in result.output


@pytest.mark.parametrize(
    ("spec_path", "expected_exit", "snippets"),
    [
        (
            "examples/cutoff_integrity/broken/forecastguard.yaml",
            1,
            ["FG-CUTOFF-001", "FG-CUTOFF-004", "FG-CUTOFF-003"],
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
    ],
)
def test_cli_advertised_examples(spec_path: str, expected_exit: int, snippets: list[str]) -> None:
    result = CliRunner().invoke(app, ["run", "--spec", str(REPO_ROOT / spec_path)])
    assert result.exit_code == expected_exit, result.output
    for snippet in snippets:
        assert snippet in result.output
