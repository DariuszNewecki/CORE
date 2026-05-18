# src/cli/commands/check/imports.py
"""
Import integrity check command — thin client over POST /v1/quality/imports.

Enforces: code.imports.must_resolve, code.imports.no_stale_namespace.
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console
from rich.table import Table

from api.cli import CoreApiClient
from cli.utils import core_command


logger = logging.getLogger(__name__)
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
    console.print("[dim]Scanning src/ for unresolvable imports (F821, F401)...[/dim]\n")
    client = CoreApiClient()
    result = await client.quality_imports()
    if result.get("status") == "ok":
        console.print("[bold green]✅ All imports resolve cleanly.[/bold green]")
        return
    violations = result.get("violations", [])
    violation_count = len(violations)
    console.print(
        f"[bold red]❌ {violation_count} unresolvable import(s) found.[/bold red]\n"
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
        console.print(table)
    console.print(
        "\n[dim]Fix: Update stale import paths or remove unused imports.[/dim]"
    )
    console.print(
        "[dim]Rule violated: code.imports.must_resolve (.intent/rules/code/imports.json)[/dim]"
    )
    raise typer.Exit(code=1)
