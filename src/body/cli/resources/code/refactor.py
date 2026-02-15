# src/body/cli/resources/code/refactor.py
# ID: 871d6b9f-4607-401b-ab97-816cda975205

import typer

from shared.cli_utils import core_command
from shared.context import CoreContext

from .hub import app


@app.command("refactor-settings")
@core_command(dangerous=True, requires_context=True, confirmation=True)
# ID: 47d02d56-dc5f-4a28-82e5-ec82d067caa0
async def refactor_settings_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Apply DI refactoring."),
    layers: str = typer.Option("mind,will", help="Comma-separated layers to process."),
):
    """
    Automated refactoring of settings imports to Dependency Injection.
    Moves layers toward using CoreContext instead of global settings.
    """
    from features.maintenance.refactor_settings_access import refactor_settings_access

    core_context: CoreContext = ctx.obj
    layer_list = [layer.strip() for layer in layers.split(",")]

    await refactor_settings_access(
        repo_path=core_context.git_service.repo_path,
        layers=layer_list,
        dry_run=not write,
    )
