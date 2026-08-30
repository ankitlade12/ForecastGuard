"""One typed report renders consistently for GitHub and SARIF."""

from __future__ import annotations

import pytest

from forecastguard.models.report import CheckResult, Report, Severity, Violation
from forecastguard.render import github_annotations, github_step_summary, report_to_sarif

pytestmark = pytest.mark.unit


def _report() -> Report:
    return Report(
        spec_name="demo",
        results=[
            CheckResult.failed(
                "runtime_leakage",
                "Runtime leakage",
                "one leak",
                [
                    Violation(
                        code="FG-LEAK-001",
                        severity=Severity.CRITICAL,
                        message="centered feature leaks",
                        location="centered",
                        evidence={
                            "source_hints": [
                                {
                                    "component": "feature",
                                    "callable_ref": "features:build",
                                    "rule": "centered-window",
                                    "message": "centered window",
                                    "line": 12,
                                    "path": "features.py",
                                }
                            ]
                        },
                    )
                ],
            ),
            CheckResult.skipped("known", "Known future", "adapter unavailable"),
        ],
    )


def test_sarif_preserves_code_severity_and_source_location() -> None:
    sarif = report_to_sarif(_report())
    runs = sarif["runs"]
    assert isinstance(runs, list)
    run = runs[0]
    assert isinstance(run, dict)
    results = run["results"]
    assert isinstance(results, list)
    result = results[0]
    assert result["ruleId"] == "FG-LEAK-001"
    assert result["level"] == "error"
    assert result["locations"][0]["physicalLocation"]["region"]["startLine"] == 12


def test_github_annotations_include_failure_and_loud_skip() -> None:
    annotations = github_annotations(_report())
    assert annotations[0].startswith("::error file=features.py,line=12")
    assert "FG-LEAK-001" in annotations[0]
    assert annotations[1].startswith("::warning")


def test_step_summary_covers_every_check() -> None:
    summary = github_step_summary(_report())
    assert "Runtime leakage" in summary
    assert "Known future" in summary
    assert "Schema: `1.0`" in summary
