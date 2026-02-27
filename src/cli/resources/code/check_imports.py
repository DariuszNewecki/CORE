# src/cli/resources/code/check_imports.py
# ID: __REPLACE_WITH_UUID__

"""
Import integrity check command.

Enforces: code.imports.must_resolve, code.imports.no_stale_namespace
Routes through ActionExecutor for constitutional compliance.
"""

from __future__ import annotations

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
# ID: __REPLACE_WITH_UUID__
# ID: d7bcc212-f4e8-4d57-a15e-95f6ac02367a
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
    console.print("[dim]Scanning src/ for unresolvable imports (F821, F401)...[/dim]\n")

    executor = ActionExecutor(core_context)
    result = await executor.execute("check.imports")

    if result.ok:
        console.print("[bold green]✅ All imports resolve cleanly.[/bold green]")
        console.print(
            f"[dim]Target: {result.data.get('target', 'src/')} "
            f"| Rules: {', '.join(result.data.get('rules_checked', []))} "
            f"| Duration: {result.duration_sec:.2f}s[/dim]"
        )
        return

    violations = result.data.get("violations", [])
    violation_count = result.data.get("violation_count", len(violations))

    console.print(
        f"[bold red]❌ {violation_count} unresolvable import(s) found.[/bold red]\n"
    )

    if violations:
        table = Table(
            title="Import Violations",
            show_header=True,
            header_style="bold red",
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

        console.print(table)

    console.print(
        "\n[dim]Fix: Update stale import paths or remove unused imports.[/dim]"
    )
    console.print(
        "[dim]Rule: code.imports.must_resolve (.intent/rules/code/imports.json)[/dim]"
    )

    raise typer.Exit(code=1)
