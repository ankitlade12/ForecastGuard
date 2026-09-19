"""ForecastGuard command-line interface (Click).

Entry point ``forecastguard`` -> :func:`app`. The ``run`` command loads a spec,
runs every check, renders the typed report, and exits non-zero when the
backtest can't be trusted — the whole point of a CI gate.
"""

from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path

import click
import pandas as pd

from forecastguard import __version__
from forecastguard.config import load_spec
from forecastguard.models.report import CheckStatus, Report
from forecastguard.models.spec import ForecastSpec
from forecastguard.planning import plan_execution, select_origins
from forecastguard.render import (
    execution_summary_lines,
    github_annotations,
    github_step_summary,
    sarif_json,
)
from forecastguard.runner import _load_frame, run_checks
from forecastguard.setup import infer_frequency, initialize, suggest_column

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
    for line in execution_summary_lines(report):
        click.echo(f"  {line}")
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
@click.option(
    "--diagnose", is_flag=True, help="Run budgeted input-specific probes after a failure."
)
@click.option(
    "--origin", "origins", multiple=True, help="Rerun only this configured raw-history origin."
)
def run(
    spec_path: str,
    strict: bool,
    output_format: str,
    json_output: str | None,
    sarif_output: str | None,
    github: bool,
    diagnose: bool,
    origins: tuple[str, ...],
) -> None:
    """Run all checks against a SPEC and exit non-zero if the backtest can't be trusted."""
    try:
        spec = load_spec(spec_path)
        spec = select_origins(spec, origins)
        if diagnose:
            spec = spec.model_copy(update={"diagnostics": True})
        # Let a feature module sitting next to the spec import (e.g. "features:build").
        sys.path.insert(0, str(Path(spec_path).resolve().parent))
        report = run_checks(spec)
        if report.failed:
            rerun = [
                "forecastguard",
                "run",
                "--spec",
                str(Path(spec_path).resolve()),
                "--strict",
                "--diagnose",
            ]
            failed_origins = sorted(
                {entry.cutoff for entry in report.coverage if entry.status == "fail"}
            )
            if failed_origins and spec.cutoff_col is None:
                rerun.extend(["--origin", failed_origins[0]])
            report.rerun_command = shlex.join(rerun)
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


@app.command(name="plan")
@click.option("--spec", "spec_path", required=True, type=click.Path(dir_okay=False))
@click.option("--format", "output_format", type=click.Choice(["human", "json"]), default="human")
@click.option("--diagnose", is_flag=True)
@click.option("--origin", "origins", multiple=True)
def plan_command(
    spec_path: str, output_format: str, diagnose: bool, origins: tuple[str, ...]
) -> None:
    """Describe data prerequisites and maximum runtime calls without executing user code."""
    try:
        spec = select_origins(load_spec(spec_path), origins)
        if diagnose:
            spec = spec.model_copy(update={"diagnostics": True})
        plan = plan_execution(spec)
    except (OSError, ValueError, TypeError, KeyError, ImportError) as exc:
        raise click.ClickException(str(exc)) from exc
    if output_format == "json":
        click.echo(plan.model_dump_json(indent=2))
    else:
        click.echo(f"ForecastGuard execution plan: {'READY' if plan.ready else 'BLOCKED'}")
        click.echo(
            f"{plan.rows} rows; {len(plan.origins)} origin(s); boundaries: {', '.join(plan.components) or 'none'}"
        )
        click.echo(
            f"Primary executions: {plan.primary_calls}; additional diagnostic limit: {plan.diagnostic_call_limit}"
        )
        for origin in plan.origins:
            click.echo(f"  Origin: {origin}")
        for prerequisite in plan.prerequisites:
            click.echo(f"  Required: {prerequisite}")
        for note in plan.notes:
            click.echo(f"  {note}")
    sys.exit(0 if plan.ready else 1)


@app.command(name="init")
@click.option("--data", "data_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--output", type=click.Path(dir_okay=False), default="forecastguard.yaml")
@click.option("--framework", type=click.Choice(["python", "mlforecast"]), default="python")
@click.option("--id-col", default=None)
@click.option("--time-col", default=None)
@click.option("--target-col", default=None)
@click.option("--freq", default=None)
@click.option("--horizon", type=click.IntRange(min=1), default=None)
@click.option("--cutoff", default=None)
@click.option(
    "--future-covariates",
    default=None,
    help="Comma-separated confirmed known-future columns; empty means none.",
)
@click.option(
    "--static-covariates",
    default=None,
    help="Comma-separated confirmed static columns; empty means none.",
)
@click.option(
    "--model-factory",
    default=None,
    help="Optional module:factory returning an unfitted MLForecast model.",
)
@click.option(
    "--no-input",
    is_flag=True,
    help="Use explicit availability roles and structural suggestions without prompts.",
)
def init_command(
    data_path: str,
    output: str,
    framework: str,
    id_col: str | None,
    time_col: str | None,
    target_col: str | None,
    freq: str | None,
    horizon: int | None,
    cutoff: str | None,
    future_covariates: str | None,
    static_covariates: str | None,
    model_factory: str | None,
    no_input: bool,
) -> None:
    """Generate a validated spec and optional runnable MLForecast wrapper."""
    try:
        frame = _load_frame(Path(data_path))
        columns = [str(column) for column in frame.columns]
        if not columns or frame.empty:
            raise ValueError("cannot initialize from an empty dataset")
        resolved = []
        for supplied, label, candidates in (
            (id_col, "Series ID column", ("unique_id", "id", "sku")),
            (time_col, "Timestamp column", ("ds", "date", "timestamp")),
            (target_col, "Target column", ("y", "sales", "value")),
        ):
            suggestion = supplied or suggest_column(columns, candidates)
            selected = (
                suggestion
                if no_input or supplied
                else click.prompt(label, default=suggestion, type=click.Choice(columns))
            )
            if selected not in columns:
                raise ValueError(f"column {selected!r} is missing")
            resolved.append(selected)
        id_col, time_col, target_col = resolved
        if horizon is None:
            if no_input:
                raise ValueError("--horizon is required with --no-input")
            horizon = click.prompt("Forecast horizon", type=click.IntRange(min=1))
        if freq is None:
            suggestion_freq = infer_frequency(frame, id_col, time_col)
            freq = (
                suggestion_freq
                if no_input
                else click.prompt("Frequency", default=suggestion_freq or "D")
            )
        if freq is None:
            raise ValueError("could not infer one regular frequency; supply --freq")
        if cutoff is None:
            dates = sorted(pd.to_datetime(frame[time_col], errors="raise").unique())
            if len(dates) <= horizon:
                raise ValueError("dataset must contain history before the requested horizon")
            suggested_cutoff = pd.Timestamp(dates[-horizon - 1]).isoformat()
            cutoff = (
                suggested_cutoff
                if no_input
                else click.prompt("Forecast cutoff", default=suggested_cutoff)
            )
        if no_input and (future_covariates is None or static_covariates is None):
            raise ValueError(
                "--no-input requires explicit --future-covariates and --static-covariates (use '' for none)"
            )
        if future_covariates is None:
            future_covariates = click.prompt(
                "Columns actually known at forecast time (comma-separated; empty for none)",
                default="",
                show_default=False,
            )
        if static_covariates is None:
            static_covariates = click.prompt(
                "Confirmed static columns (comma-separated; empty for none)",
                default="",
                show_default=False,
            )
        if model_factory and framework != "mlforecast":
            raise ValueError("--model-factory requires --framework mlforecast")
        spec = ForecastSpec(
            data=Path(data_path).resolve(),
            id_col=id_col,
            time_col=time_col,
            target_col=target_col,
            cutoff=cutoff,
            horizon=horizon,
            freq=freq,
            future_covariates=[c.strip() for c in future_covariates.split(",") if c.strip()],
            static_covariates=[c.strip() for c in static_covariates.split(",") if c.strip()],
            perturbations=["nullify", "noise", "sign_flip"],
        )
        result = initialize(
            spec, frame, Path(output), framework=framework, model_factory=model_factory
        )
    except (OSError, ValueError, TypeError, KeyError, ImportError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Created {result.spec_path}")
    if result.wrapper_path:
        click.echo(f"Created {result.wrapper_path}; install forecastguard[nixtla] to execute it.")
        if not model_factory:
            click.echo(
                "The generated wrapper uses a starter model; connect your own model factory to validate your pipeline."
            )
    else:
        click.echo("Add feature_fn, forecast_fn or pipeline_factory to enable runtime coverage.")
    click.echo("Unlisted covariates remain past-only. Review declared availability before running.")
    click.echo(shlex.join(["forecastguard", "plan", "--spec", str(result.spec_path)]))


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
