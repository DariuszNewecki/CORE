# src/cli/commands/fix/modularity.py
"""
Automated Modularity Healing.
Connects Modularity Diagnostics to the A3 Autonomous Loop.

CONSTITUTIONAL ALIGNMENT:
- Removed legacy error decorators to prevent circular imports.
- Triggers autonomous architectural improvement via develop_from_goal.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.table import Table

from cli.utils import core_command
from shared.context import CoreContext

from . import fix_app


@fix_app.command("modularity", help="Autonomously modularize architectural offenders.")
@core_command(dangerous=True, confirmation=True)
# ID: ea078c28-eb5f-46ec-b39c-e55cf33714ed
async def fix_modularity_cmd(
    ctx: typer.Context,
    min_score: float = typer.Option(
        None,
        "--score",
        help="Minimum score to trigger healing (defaults to Constitution)",
    ),
    limit: int = typer.Option(
        1, "--limit", "-n", help="Max files to heal in one batch"
    ),
    write: bool = typer.Option(False, "--write", help="Apply changes autonomously"),
):
    """
    Finds high-complexity files and uses the A3 loop to modularize them.
    """
    from will.self_healing.modularity_remediation_service import (
        ModularityRemediationService,
    )

    core_context: CoreContext = ctx.obj
    service = ModularityRemediationService(core_context)
    with logger.info("[bold cyan]CORE is defragmenting architecture...[/bold cyan]"):
        results = await service.remediate_batch(
            min_score=min_score, limit=limit, write=write
        )
    if not results:
        logger.info("[green]✅ No files exceed the modularity threshold.[/green]")
        return
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
    logger.info(table)
