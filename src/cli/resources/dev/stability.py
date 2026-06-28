# src/cli/resources/dev/stability.py
"""
Stability CLI Commands - Phase 2 Hardening.
Orchestrates idempotency testing for atomic actions.
"""

from __future__ import annotations

import typer
from rich.console import Console

from body.maintenance.idempotency_harness import IdempotencyHarness
from cli.utils import core_command
from shared.cli.command_meta import (
    CommandBehavior,
    CommandExposure,
    CommandLayer,
    command_meta,
)

from .hub import app


console = Console()


@app.command("test-stability")
@command_meta(
    canonical_name="dev.test-stability",
    behavior=CommandBehavior.VALIDATE,
    layer=CommandLayer.WILL,
    exposure=CommandExposure.USER_FACING,
    summary="Verify the idempotency (stability) of a specific atomic action.",
)
@core_command(dangerous=True, requires_context=True)
# ID: b6bb979d-bb7f-4a4d-8518-1bd977634891
async def dev_stability_cmd(
    ctx: typer.Context,
    action_id: str = typer.Argument(
        ..., help="The ID of the action to test (e.g. fix.format)."
    ),
) -> None:
    """
    Runs a stability trial on an action:
    1. Runs the action once to apply changes.
    2. Snapshots the codebase.
    3. Runs the action again.
    4. Verifies that the second run resulted in ZERO changes.
    """
    core_context = ctx.obj
    harness = IdempotencyHarness(core_context)
    console.print(
        f"\n[bold cyan]🧪 Initiating Stability Trial: {action_id}[/bold cyan]\n"
    )
    result = await harness.verify_action(action_id)
    if result.ok:
        console.print(
            f"\n[bold green]✅ PROVEN:[/bold green] Action '{action_id}' is idempotent and stable."
        )
    else:
        console.print(
            f"\n[bold red]❌ FAILED:[/bold red] Action '{action_id}' is unstable (logic drift detected)."
        )
        for error in result.errors:
            console.print(f"  [yellow]![/yellow] {error}")
        raise typer.Exit(code=1)
