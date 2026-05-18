# src/cli/resources/code/fix_atomic.py
import logging

import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.utils import core_command
from shared.cli.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


logger = logging.getLogger(__name__)
console = Console()


@app.command("fix-atomic")
@command_meta(
    canonical_name="code.fix-atomic",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.BODY,
    summary="Heal violations in the Atomic Action pattern.",
    dangerous=True,
)
@core_command(dangerous=True, requires_context=False)
# ID: 1a0797b9-e800-4783-9305-158b5f9247af
async def fix_atomic_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply fixes to atomic action patterns."
    ),
) -> None:
    """
    Heal violations in the Atomic Action pattern.
    Ensures @atomic_action decorators and ActionResult returns are present.
    """
    client = CoreApiClient()
    initial = await client.run_fix("fix.atomic_actions", write=write)
    run_id = initial.get("run_id")
    if not run_id:
        console.print(f"[red]fix.atomic_actions failed to dispatch: {initial}[/red]")
        raise typer.Exit(1)
    final = await client._poll_run(run_id)
    if final.get("status") == "completed":
        console.print("[green]✓ fix.atomic_actions completed.[/green]")
        return
    console.print(
        f"[red]fix.atomic_actions failed: {final.get('error') or final}[/red]"
    )
    raise typer.Exit(1)
