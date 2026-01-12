# src/body/cli/commands/fix/modularity.py

"""
Automated Modularity Healing.
Connects Modularity Diagnostics to the A3 Autonomous Loop.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from shared.cli_utils import core_command
from shared.context import CoreContext

from . import fix_app, handle_command_errors


console = Console()


@fix_app.command("modularity", help="Autonomously modularize architectural offenders.")
@handle_command_errors
@core_command(dangerous=True, confirmation=True)
# ID: d958ae30-2f04-4924-ada2-41b95a1f9a1e
async def fix_modularity_cmd(
    ctx: typer.Context,
    min_score: float = typer.Option(
        65.0, "--score", help="Minimum score to trigger healing"
    ),
    limit: int = typer.Option(
        1, "--limit", "-n", help="Max files to heal in one batch"
    ),
    write: bool = typer.Option(False, "--write", help="Apply changes autonomously"),
):
    """
    Finds high-complexity files and uses the A3 loop to modularize them.
    """
    from features.self_healing.modularity_remediation_service import (
        ModularityRemediationService,
    )

    core_context: CoreContext = ctx.obj
    service = ModularityRemediationService(core_context)

    with console.status("[bold cyan]CORE is defragmenting architecture...[/bold cyan]"):
        results = await service.remediate_batch(
            min_score=min_score, limit=limit, write=write
        )

    if not results:
        console.print("[green]✅ No files exceed the modularity threshold.[/green]")
        return

    # Results Table
    table = Table(title="Modularity Healing Results")
    table.add_column("File", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Initial", justify="right")
    table.add_column("Final", justify="right")
    table.add_column("Delta", style="green", justify="right")

    for res in results:
        status = "✅" if res["success"] else "❌"
        delta = res["improvement"]
        table.add_row(
            res["file"],
            status,
            f"{res['start_score']:.1f}",
            f"{res['final_score']:.1f}",
            f"-{delta:.1f}" if delta > 0 else "0.0",
        )

    console.print(table)
