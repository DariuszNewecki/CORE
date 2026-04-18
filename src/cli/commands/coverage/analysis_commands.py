# src/cli/commands/coverage/analysis_commands.py
"""Coverage analysis commands - history and method comparison."""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cli.utils import core_command
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()


# ID: dc3466dd-9962-4fc9-94c7-c68021ecee26
def register_analysis_commands(app: typer.Typer) -> None:
    """Register coverage analysis commands."""
    app.command("history")(coverage_history)
    app.command("compare-methods")(compare_methods_command)


@core_command(dangerous=False)
# ID: e2676de4-1e05-4408-9cbe-a70795cf3417
def coverage_history(
    ctx: typer.Context,
    limit: int = typer.Option(
        10, "--limit", "-n", help="Number of history entries to show"
    ),
) -> None:
    """
    Shows coverage history and trends from the Mind's history records.
    """
    core_context: CoreContext = ctx.obj
    history_file = (
        core_context.file_handler.repo_path
        / "var"
        / "mind"
        / "history"
        / "coverage_history.json"
    )
    if not history_file.exists():
        logger.info("[yellow]No coverage history found[/yellow]")
        return
    try:
        history_data = json.loads(history_file.read_text())
        runs = history_data.get("runs", [])
        last_run = history_data.get("last_run", {})
        if not runs and (not last_run):
            logger.info("[yellow]History file is empty[/yellow]")
            return
        logger.info("[bold]📈 Coverage History[/bold]\n")
        if last_run:
            logger.info(
                "  Latest Run: [cyan]%s%[/cyan]", last_run.get("overall_percent", 0)
            )
        if runs:
            table = Table(box=None)
            table.add_column("Date", style="dim")
            table.add_column("Coverage", justify="right")
            table.add_column("Delta", justify="right")
            for run in runs[-limit:]:
                delta = run.get("delta", 0)
                color = "green" if delta >= 0 else "red"
                table.add_row(
                    run.get("timestamp", "Unknown")[:16],
                    f"{run.get('overall_percent', 0)}%",
                    f"[{color}]{delta:+.1f}%[/{color}]",
                )
            logger.info(table)
    except Exception as e:
        logger.info("[red]Error reading history: %s[/red]", e)
        raise typer.Exit(code=1)


@core_command(dangerous=False)
# ID: 76d6a0c8-0e28-4de6-be76-0630526e54c0
async def compare_methods_command(ctx: typer.Context) -> None:
    """
    Compare legacy (accumulate) vs new (adaptive) test generation methods.
    """
    comparison_text = "[bold]OLD: Accumulative (V1)[/bold]\n  Architecture: Monolithic (~800 lines)\n  Learning: None (repeats same mistakes)\n  Strategy: Fixed\n  Success rate: ~0% on complex files\n\n[bold]NEW: Adaptive (V2)[/bold]\n  Architecture: Component-based (6 small components)\n  Learning: Pattern recognition (switches after 3 failures)\n  Strategy: Adaptive (file-type aware)\n  Success rate: ~57% on complex files\n\n[bold]Key Improvements:[/bold]\n  ✓ File analysis before generation\n  ✓ Failure pattern recognition\n  ✓ Automatic strategy switching"
    logger.info(
        Panel(
            comparison_text,
            title="📊 Method Comparison",
            border_style="cyan",
            expand=False,
        )
    )
