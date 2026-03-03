# src/cli/resources/code/fix_atomic.py

import typer

from shared.cli_utils import core_command
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


@app.command("fix-atomic")
@command_meta(
    canonical_name="code.fix-atomic",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.BODY,
    summary="Heal violations in the Atomic Action pattern.",
    dangerous=True,
)
@core_command(dangerous=True, requires_context=True)
# ID: 1a0797b9-e800-4783-9305-158b5f9247af
async def fix_atomic_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply fixes to atomic action patterns."
    ),
):
    """
    Heal violations in the Atomic Action pattern.
    Ensures @atomic_action decorators and ActionResult returns are present.
    """
    # Routes to fix.atomic_actions atomic action
    await ctx.obj.action_executor.execute("fix.atomic_actions", write=write)
