"""Integration tests: the runner + CLI run end to end on the quickstart example."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from forecastguard.cli import app
from forecastguard.config import load_spec
from forecastguard.runner import run_checks
from tests.conftest import QUICKSTART_SPEC

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
