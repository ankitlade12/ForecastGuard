"""ForecastGuard command-line interface (Click).

Entry point ``forecastguard`` -> :func:`app`. The ``run`` command loads a spec,
runs every check, renders the typed report, and exits non-zero when the
backtest can't be trusted — the whole point of a CI gate.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from forecastguard import __version__
from forecastguard.config import load_spec
from forecastguard.models.report import CheckStatus, Report
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
def run(spec_path: str, strict: bool) -> None:
    """Run all checks against a SPEC and exit non-zero if the backtest can't be trusted."""
    try:
        spec = load_spec(spec_path)
        # Let a feature module sitting next to the spec import (e.g. "features:build").
        sys.path.insert(0, str(Path(spec_path).resolve().parent))
        report = run_checks(spec)
    except (FileNotFoundError, ValueError, TypeError, ImportError) as exc:
        raise click.ClickException(str(exc)) from exc
    _render(report)
    code = report.exit_code(strict=strict)
    verdict = "PASS" if code == 0 else "FAIL"
    click.echo(f"  {verdict} - exit {code}")
    sys.exit(code)


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
