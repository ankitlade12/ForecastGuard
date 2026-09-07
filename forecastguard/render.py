"""Render one typed Report for human, GitHub, JSON, and SARIF consumers."""

from __future__ import annotations

import json
from typing import Any

from forecastguard.models.report import CheckStatus, Report, Severity, Violation


def report_to_sarif(report: Report) -> dict[str, object]:
    """Convert a report to SARIF 2.1.0 without changing its verdict."""
    violations = [item for result in report.results for item in result.violations]
    rules = {
        item.code: {
            "id": item.code,
            "shortDescription": {"text": item.message},
            "properties": {"severity": item.severity.value},
        }
        for item in violations
    }
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "ForecastGuard",
                        "informationUri": "https://github.com/ankitlade12/ForecastGuard",
                        "rules": list(rules.values()),
                    }
                },
                "results": [_sarif_result(item) for item in violations],
                "properties": {
                    "forecastguardSchemaVersion": report.schema_version,
                    "checks": [result.model_dump(mode="json") for result in report.results],
                },
            }
        ],
    }


def sarif_json(report: Report) -> str:
    return json.dumps(report_to_sarif(report), indent=2)


def github_annotations(report: Report) -> list[str]:
    """Return GitHub workflow commands for failures, errors, and loud skips."""
    commands: list[str] = []
    for result in report.results:
        for violation in result.violations:
            properties: list[str] = []
            properties.append(f"title={_escape_property(violation.code)}")
            commands.append(f"::error {','.join(properties)}::{_escape_message(violation.message)}")
        if result.status is CheckStatus.SKIPPED or (
            result.status is CheckStatus.FAIL and result.detail
        ):
            label = " skipped" if result.status is CheckStatus.SKIPPED else " incomplete"
            commands.append(
                f"::warning title={_escape_property(result.name + label)}::"
                f"{_escape_message(result.detail or result.summary)}"
            )
        elif result.status is CheckStatus.ERROR:
            commands.append(
                f"::error title={_escape_property(result.name + ' error')}::"
                f"{_escape_message(result.detail or result.summary)}"
            )
    return commands


def github_step_summary(report: Report) -> str:
    """Compact Markdown summary suitable for ``GITHUB_STEP_SUMMARY``."""
    lines = ["## ForecastGuard", "", "| Check | Status | Summary |", "|---|---:|---|"]
    for result in report.results:
        summary = result.summary + (f"; {result.detail}" if result.detail else "")
        lines.append(
            f"| {result.name} | {result.status.value.upper()} | "
            f"{str(summary or '').replace('|', '\\|')} |"
        )
    violations = sum(len(result.violations) for result in report.results)
    lines.extend(["", f"Violations: **{violations}** · Schema: `{report.schema_version}`", ""])
    return "\n".join(lines)


def _sarif_result(violation: Violation) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ruleId": violation.code,
        "level": _sarif_level(violation.severity),
        "message": {"text": violation.message},
        "properties": {
            "severity": violation.severity.value,
            "location": violation.location,
            "evidence": violation.evidence,
        },
    }
    return result


def _sarif_level(severity: Severity) -> str:
    if severity in (Severity.CRITICAL, Severity.HIGH):
        return "error"
    if severity in (Severity.MEDIUM, Severity.LOW):
        return "warning"
    return "note"


def _escape_message(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(value: str) -> str:
    return _escape_message(value).replace(":", "%3A").replace(",", "%2C")
