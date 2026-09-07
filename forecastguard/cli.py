"""ForecastGuard command-line interface (Click).

Entry point ``forecastguard`` -> :func:`app`. The ``run`` command loads a spec,
runs every check, renders the typed report, and exits non-zero when the
backtest can't be trusted — the whole point of a CI gate.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click

from forecastguard import __version__
from forecastguard.config import load_spec
from forecastguard.models.report import CheckStatus, Report
from forecastguard.render import github_annotations, github_step_summary, sarif_json
from forecastguard.runner import run_checks

_STATUS_GLYPH: dict[CheckStatus, str] = {
    CheckStatus.PASS: "PASS",
    CheckStatus.FAIL: "FAIL",
    CheckStatus.SKIPPED: "SKIP",
    CheckStatus.ERROR: "ERR ",
}


def _render(report: Report) -> None:
    """Print a human-readable summary of a report to stdout."""
    click.echo("")
    click.echo("  ForecastGuard CI")
    if report.spec_name:
        click.echo(f"  spec: {report.spec_name}")
    click.echo("")
    for result in report.results:
        click.echo(f"  [{_STATUS_GLYPH[result.status]}] {result.name}")
        if result.status is CheckStatus.SKIPPED and result.detail:
            click.echo(f"         - {result.detail}")
        for violation in result.violations:
            loc = f" ({violation.location})" if violation.location else ""
            click.echo(
                f"         * {violation.severity.value}: "
                f"{violation.message}{loc} [{violation.code}]"
            )
        if result.status is CheckStatus.ERROR and result.detail:
            last_line = result.detail.strip().splitlines()[-1]
            click.echo(f"         - {last_line}")
        elif result.status is CheckStatus.FAIL and result.detail:
            click.echo(f"         - Incomplete: {result.detail}")
    click.echo("")


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="forecastguard")
def app() -> None:
    """ForecastGuard CI — the quality gate for forecasting backtests."""


@app.command()
@click.option(
    "--spec",
    "spec_path",
    required=True,
    type=click.Path(dir_okay=False),
    help="Path to forecastguard.yaml.",
)
@click.option("--strict", is_flag=True, help="Treat loud skips as failures.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["human", "json"], case_sensitive=False),
    default="human",
    show_default=True,
    help="Report output format.",
)
@click.option(
    "--json-output",
    type=click.Path(dir_okay=False),
    help="Also write the versioned JSON report to this path.",
)
@click.option(
    "--sarif-output",
    type=click.Path(dir_okay=False),
    help="Also write a SARIF 2.1.0 report to this path.",
)
@click.option("--github", is_flag=True, help="Emit GitHub annotations and step summary.")
def run(
    spec_path: str,
    strict: bool,
    output_format: str,
    json_output: str | None,
    sarif_output: str | None,
    github: bool,
) -> None:
    """Run all checks against a SPEC and exit non-zero if the backtest can't be trusted."""
    try:
        spec = load_spec(spec_path)
        # Let a feature module sitting next to the spec import (e.g. "features:build").
        sys.path.insert(0, str(Path(spec_path).resolve().parent))
        report = run_checks(spec)
    except (FileNotFoundError, ValueError, TypeError, ImportError) as exc:
        raise click.ClickException(str(exc)) from exc
    code = report.exit_code(strict=strict)
    if json_output is not None:
        Path(json_output).write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    if sarif_output is not None:
        Path(sarif_output).write_text(sarif_json(report) + "\n", encoding="utf-8")
    if github:
        for command in github_annotations(report):
            click.echo(command, err=output_format == "json")
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_path:
            with Path(summary_path).open("a", encoding="utf-8") as handle:
                handle.write(github_step_summary(report))
    if output_format == "json":
        click.echo(report.model_dump_json(indent=2))
        sys.exit(code)

    _render(report)
    verdict = "PASS" if code == 0 else "FAIL"
    click.echo(f"  {verdict} - exit {code}")
    sys.exit(code)


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
