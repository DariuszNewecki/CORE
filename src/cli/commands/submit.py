# src/body/cli/commands/submit.py
# ID: 2bd6fcc9-9752-420a-a48e-35963a672ef0

"""DEPRECATED: Use 'core-admin proposals integrate' instead."""

from __future__ import annotations

import typer

from shared.cli_utils import deprecated_command


submit_app = typer.Typer(
    help="[DEPRECATED] Use 'proposals' resource.", no_args_is_help=True
)


@submit_app.command("changes")
# ID: ce382b1a-af48-4e9b-bcd9-ce8938b58d51
def integrate_command(ctx: typer.Context, message: str = typer.Option(..., "-m")):
    """DEPRECATED shim for proposals integrate."""
    deprecated_command("submit changes", "proposals integrate")
    # Forward to the new command logic if needed, or simply exit.
    raise typer.Exit(1)
