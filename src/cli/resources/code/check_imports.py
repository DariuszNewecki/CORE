# src/cli/resources/code/check_imports.py
"""
Import integrity check command.

Enforces: code.imports.must_resolve, code.imports.no_stale_namespace
Routes through ActionExecutor for constitutional compliance.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console
from rich.table import Table

from body.atomic.executor import ActionExecutor
from shared.cli_utils import core_command
from shared.context import CoreContext

from .hub import app


console = Console()


@app.command("check-imports")
@core_command(dangerous=False, requires_context=True)
# ID: 53db749b-a5cf-44e4-8e7f-47e6499aec0b
async def check_imports_cmd(ctx: typer.Context) -> None:
    """
    Verify all import statements resolve to existing modules.

    Checks for:
    - F821: References to undefined names (moved/deleted modules)
    - F401: Stale imports left after refactoring

    Enforces:
    - code.imports.must_resolve
    - code.imports.no_stale_namespace
    """
    core_context: CoreContext = ctx.obj
    console.rule("[bold cyan]Import Integrity Check[/bold cyan]")
    logger.info("[dim]Scanning src/ for unresolvable imports (F821, F401)...[/dim]\n")
    executor = ActionExecutor(core_context)
    result = await executor.execute("check.imports")
    if result.ok:
        logger.info("[bold green]✅ All imports resolve cleanly.[/bold green]")
        logger.info(
            "[dim]Target: %s | Rules: %s | Duration: %ss[/dim]",
            result.data.get("target", "src/"),
            ", ".join(result.data.get("rules_checked", [])),
            result.duration_sec,
        )
        return
    violations = result.data.get("violations", [])
    violation_count = result.data.get("violation_count", len(violations))
    logger.info(
        "[bold red]❌ %s unresolvable import(s) found.[/bold red]\n", violation_count
    )
    if violations:
        table = Table(
            title="Import Violations", show_header=True, header_style="bold red"
        )
        table.add_column("File", style="cyan", overflow="fold")
        table.add_column("Line", style="yellow", justify="right", width=6)
        table.add_column("Rule", style="magenta", width=6)
        table.add_column("Message", style="white", overflow="fold")
        for v in violations:
            table.add_row(
                v.get("file", ""),
                str(v.get("line", "")),
                v.get("rule", ""),
                v.get("message", ""),
            )
        logger.info(table)
    logger.info("\n[dim]Fix: Update stale import paths or remove unused imports.[/dim]")
    logger.info(
        "[dim]Rule: code.imports.must_resolve (.intent/rules/code/imports.json)[/dim]"
    )
    raise typer.Exit(code=1)
