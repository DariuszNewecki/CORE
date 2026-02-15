# src/body/cli/resources/code/audit_duplicates.py
import typer

from shared.cli_utils import core_command

from .hub import app


@app.command("audit-duplicates")
@core_command(dangerous=False, requires_context=True)
# ID: 2ad098e5-aa8a-4e12-89e4-be20d2e12e03
async def audit_duplicates_cmd(
    ctx: typer.Context,
    threshold: float = typer.Option(0.96, help="Similarity threshold (0.0-1.0)."),
):
    """
    Perform a semantic scan to find duplicate logic across the codebase.
    Helps enforce the 'dry_by_design' constitutional principle.
    """
    from body.cli.logic.duplicates import inspect_duplicates_async

    await inspect_duplicates_async(context=ctx.obj, threshold=threshold)
