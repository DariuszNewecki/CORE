# src/cli/resources/dev/stability.py
"""
Stability CLI Commands - Phase 2 Hardening.
Orchestrates idempotency testing for atomic actions.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from body.maintenance.idempotency_harness import IdempotencyHarness
from shared.cli_utils import core_command
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


console = Console()


@app.command("test-stability")
@command_meta(
    canonical_name="dev.test-stability",
    behavior=CommandBehavior.VALIDATE,
    layer=CommandLayer.WILL,
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
    logger.info(
        "\n[bold cyan]🧪 Initiating Stability Trial: %s[/bold cyan]\n", action_id
    )
    result = await harness.verify_action(action_id)
    if result.ok:
        logger.info(
            "\n[bold green]✅ PROVEN:[/bold green] Action '%s' is idempotent and stable.",
            action_id,
        )
    else:
        logger.info(
            "\n[bold red]❌ FAILED:[/bold red] Action '%s' is unstable (logic drift detected).",
            action_id,
        )
        for error in result.errors:
            logger.info("  [yellow]![/yellow] %s", error)
        raise typer.Exit(code=1)
