# src/cli/commands/check/diagnostics_commands.py
"""
Diagnostic and contract verification commands.

Thin clients over /v1/quality/* (ADR-055 D6 Batch C3). Policy coverage
and Body UI contract checks both execute server-side; this module
renders the responses.
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.logic.diagnostics_policy import policy_coverage
from cli.utils import core_command


logger = logging.getLogger(__name__)
console = Console()


@core_command(dangerous=False)
# ID: 2d3aad66-4285-48c7-b65d-f32ab7f86a01
async def diagnostics_cmd(ctx: typer.Context) -> None:
    """
    Audit the constitution for policy coverage and structural integrity.
    """
    _ = ctx
    await policy_coverage()


@core_command(dangerous=False)
# ID: a2eeec63-e811-4430-8e97-7d317bd0c384
async def check_body_ui_cmd(ctx: typer.Context) -> None:
    """
    Check for Body layer UI contract violations (print, rich usage, os.environ).

    Body modules must be HEADLESS.
    """
    _ = ctx
    console.print("[bold cyan]🔍 Checking Body UI Contracts...[/bold cyan]")
    client = CoreApiClient()
    result = await client.quality_body_ui()
    if result.get("status") == "ok":
        console.print("[green]✅ Body contracts compliant.[/green]")
        return

    violations = result.get("violations", [])
    console.print(f"\n[red]❌ Found {len(violations)} contract violations:[/red]\n")
    by_file: dict[str, list[dict]] = {}
    for v in violations:
        path = v.get("file", "unknown")
        by_file.setdefault(path, []).append(v)
    for path, file_violations in by_file.items():
        console.print(f"[bold]{path}[/bold]:")
        for v in file_violations:
            rule = v.get("rule_id", "unknown")
            msg = v.get("message", "")
            line = v.get("line")
            loc = f"line {line}" if line else "general"
            console.print(f"  - [{rule}] {msg} ({loc})")
        console.print()
    console.print(
        "[yellow]💡 Run 'core-admin fix body-ui --write' to auto-fix.[/yellow]"
    )
    raise typer.Exit(1)
