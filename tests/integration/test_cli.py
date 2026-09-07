"""Integration tests: the runner + CLI run end to end on the quickstart example."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from forecastguard.checks.protocol import CheckContext
from forecastguard.cli import app
from forecastguard.config import load_spec
from forecastguard.models.report import CheckResult, Report
from forecastguard.runner import run_checks
from tests.conftest import QUICKSTART_SPEC, REPO_ROOT

pytestmark = pytest.mark.integration


def test_default_runner_uses_registered_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    class RegisteredCheck:
        check_id = "registered_check"
        name = "Registered check"

        def run(self, ctx: CheckContext) -> CheckResult:
            return CheckResult.passed(self.check_id, self.name, "executed")

    monkeypatch.setattr("forecastguard.runner.default_checks", lambda: [RegisteredCheck()])
    report = run_checks(load_spec(QUICKSTART_SPEC))
    assert [result.check_id for result in report.results] == ["registered_check"]


def test_invalid_data_does_not_resolve_user_code(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected(_ref: str) -> None:
        pytest.fail("user code was resolved before structural validation")

    monkeypatch.setattr("forecastguard.runner._resolve_callable", unexpected)
    spec = load_spec(REPO_ROOT / "examples/cutoff_integrity/broken/forecastguard.yaml")
    spec = spec.model_copy(update={"forecast_fn": "user:predict"})
    report = run_checks(spec)
    assert report.failed
    assert report.has_skips


def test_runtime_budget_does_not_import_user_code(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected(_ref: str) -> None:
        pytest.fail("budget exceeded but user code was imported")

    monkeypatch.setattr("forecastguard.runner._resolve_callable", unexpected)
    spec = load_spec(QUICKSTART_SPEC).model_copy(
        update={"forecast_fn": "user:predict", "max_probe_calls": 0}
    )
    report = run_checks(spec)
    assert "no probes executed" in (report.results[-1].detail or "")
    assert report.exit_code(strict=True) == 1


def test_adapter_failure_prevents_runtime_import(monkeypatch: pytest.MonkeyPatch) -> None:
    from forecastguard.models.spec import MLForecastAdapterSpec

    def fail_adapter(*args: object) -> None:
        raise ValueError("adapter unavailable")

    def unexpected(_ref: str) -> None:
        pytest.fail("runtime imported despite failed adapter")

    monkeypatch.setattr("forecastguard.runner.inspect_mlforecast", fail_adapter)
    monkeypatch.setattr("forecastguard.runner._resolve_callable", unexpected)
    spec = load_spec(QUICKSTART_SPEC).model_copy(
        update={
            "adapter": MLForecastAdapterSpec(model_fn="user:factory"),
            "forecast_fn": "user:predict",
        }
    )
    report = run_checks(spec)
    assert report.has_skips
    assert report.exit_code(strict=True) == 1


def test_github_json_stdout_remains_parseable() -> None:
    result = CliRunner().invoke(
        app, ["run", "--spec", str(QUICKSTART_SPEC), "--github", "--format", "json"]
    )
    assert json.loads(result.stdout)["schema_version"] == "1.0"
    assert "::warning" in result.stderr


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
