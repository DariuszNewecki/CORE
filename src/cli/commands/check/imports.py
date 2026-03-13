# src/cli/commands/check/imports.py
"""
Import integrity check command.

Enforces: code.imports.must_resolve, code.imports.no_stale_namespace
Delegates to: body.atomic.check_actions.action_check_imports
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console
from rich.table import Table

from body.atomic.check_actions import action_check_imports
from shared.cli_utils import core_command


console = Console()


@core_command(dangerous=False, requires_context=False)
# ID: 90ad21a4-b24a-4247-aeb5-3abf13cb45ae
async def imports_cmd(ctx: typer.Context) -> None:
    """
    Verify all import statements resolve to existing modules.

    Checks for:
    - F821: References to undefined names (moved/deleted modules)
    - F401: Stale imports left after refactoring

    Enforces constitutional rules:
    - code.imports.must_resolve
    - code.imports.no_stale_namespace
    """
    _ = ctx
    console.rule("[bold cyan]Import Integrity Check[/bold cyan]")
    logger.info("[dim]Scanning src/ for unresolvable imports (F821, F401)...[/dim]\n")
    result = await action_check_imports()
    if result.ok:
        logger.info("[bold green]✅ All imports resolve cleanly.[/bold green]")
        logger.info(
            "[dim]Checked: %s | Rules: %s | Duration: %ss[/dim]",
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
        "[dim]Rule violated: code.imports.must_resolve (.intent/rules/code/imports.json)[/dim]"
    )
    raise typer.Exit(code=1)
