"""Health CLI commands for the NeuroCognitive Architecture (NCA).

Purpose:
    Provide operator-focused commands for inspecting live health information and
    presenting the aggregated status of registered NCA components.
External Dependencies:
    Uses the `rich` console library for terminal rendering. No HTTP requests or
    subprocess invocations are performed.
Fallback Semantics:
    When health aggregation fails, the command surfaces the exception details to
    the operator and exits with a non-zero code instead of attempting silent
    fallbacks.
Timeout Strategy:
    Health checks run synchronously and inherit timeout behaviour from the
    underlying monitoring subsystem; the CLI does not impose additional timers.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import typer
from rich.console import Console
from rich.table import Table

from neuroca.monitoring.health import HealthStatus, SystemHealthSummary, run_health_checks

logger = logging.getLogger(__name__)
console = Console()

# Create a Typer app for health commands
health_app = typer.Typer(name="health", help="Monitor and manage system health dynamics.")

_STATUS_STYLES: Dict[HealthStatus, str] = {
    HealthStatus.HEALTHY: "green",
    HealthStatus.DEGRADED: "yellow",
    HealthStatus.UNHEALTHY: "red",
    HealthStatus.CRITICAL: "bold red",
    HealthStatus.UNKNOWN: "dim",
}


def _status_style(status: HealthStatus) -> str:
    """
    Determine the Rich style token for a component health status.

    Summary:
        Maps a ``HealthStatus`` enum member to a style string understood by
        the Rich console renderer.
    Parameters:
        status (HealthStatus): Status value reported by the monitoring layer.
    Returns:
        str: Style token applied to console output.
    Raises:
        None
    Side Effects:
        None. Performs a pure dictionary lookup.
    Timeout/Retry Notes:
        Not applicable.
    """
    return _STATUS_STYLES.get(status, "white")


def _format_metrics(metrics: dict[str, Any]) -> str:
    """
    Convert the metrics dictionary into a compact printable string.

    Summary:
        Joins key-value pairs into a comma-separated list for CLI readability.
    Parameters:
        metrics (dict[str, Any]): Metrics emitted by a component health check.
    Returns:
        str: Dash (``-``) when no metrics exist, otherwise a formatted list.
    Raises:
        None
    Side Effects:
        None. Operates on the provided mapping only.
    Timeout/Retry Notes:
        Not applicable.
    """
    if not metrics:
        return "-"
    return ", ".join(f"{key}={value}" for key, value in metrics.items())


def _render_component_table(summary: SystemHealthSummary) -> Table:
    """
    Build a Rich table summarising component-level health results.

    Summary:
        Generates a tabular representation of component statuses, details, and
        metrics for display in the CLI.
    Parameters:
        summary (SystemHealthSummary): Aggregated health data from the monitoring layer.
    Returns:
        Table: Rich table instance ready for rendering.
    Raises:
        None
    Side Effects:
        None. Returns a new table object without modifying input data.
    Timeout/Retry Notes:
        Not applicable.
    """
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Component")
    table.add_column("Status")
    table.add_column("Details", overflow="fold")
    table.add_column("Metrics", overflow="fold")

    for component_id, result in summary.component_results.items():
        status_style = _status_style(result.status)
        table.add_row(
            component_id,
            f"[{status_style}]{result.status.value}[/]",
            result.details or "-",
            _format_metrics(result.metrics),
        )

    return table


@health_app.command("status")
def health_status() -> None:
    """Display the current aggregate health status of the NCA deployment.

    Summary:
        Executes the registered health checks, summarises the overall system
        state, and renders component-level information in a tabular format.
    Parameters:
        None
    Returns:
        None
    Raises:
        typer.Exit: Raised with a non-zero exit code when health aggregation
            fails and the results cannot be presented.
    Side Effects:
        Emits structured log messages and writes formatted output to stdout.
    Timeout/Retry Notes:
        Relies on the monitoring subsystem's internal timeouts; no retries are
        attempted by this command.
    """
    logger.info("Retrieving system health summary via monitoring subsystem.")

    try:
        summary = run_health_checks()
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Failed to retrieve system health summary: %s", exc)
        console.print(f"[bold red]Error:[/] unable to retrieve system health — {exc}")
        raise typer.Exit(code=1) from exc

    overall_style = _status_style(summary.status)
    console.print(f"[bold {overall_style}]Overall status: {summary.status.value.upper()}[/]")
    console.print(f"Checked at: {summary.timestamp.isoformat()}\n")

    if summary.details:
        console.print(f"[italic]{summary.details}[/]\n")

    if not summary.component_results:
        console.print("[yellow]No components are currently registered for health monitoring.[/]")
        return

    console.print(_render_component_table(summary))

    degraded_components = [
        (component_id, result) for component_id, result in summary.component_results.items()
        if result.status in {HealthStatus.DEGRADED, HealthStatus.UNHEALTHY, HealthStatus.CRITICAL}
    ]

    if degraded_components:
        console.print("\n[bold yellow]Attention required for the following components:[/]")
        for component_id, result in degraded_components:
            console.print(
                f" - {component_id}: {result.status.value} — {result.details or 'No additional details provided.'}"
            )

