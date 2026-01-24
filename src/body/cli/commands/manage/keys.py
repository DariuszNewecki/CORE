# src/body/cli/commands/manage/keys.py

"""Refactored logic for src/body/cli/commands/manage/keys.py."""

from __future__ import annotations

import typer

from mind.governance.key_management_service import KeyManagementError, keygen
from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.path_resolver import PathResolver


keys_sub_app = typer.Typer(
    help="Manage operator cryptographic keys.", no_args_is_help=True
)


@keys_sub_app.command("generate")
@core_command(dangerous=False)
# ID: accf98d6-6375-4fd5-87f1-6a6e5cbf3672
def keygen_command(
    ctx: typer.Context, identity: str = typer.Argument(...), force: bool = False
):
    """Generate a new Ed25519 key pair."""
    core_context: CoreContext = ctx.obj
    path_resolver = PathResolver.from_repo(
        repo_root=core_context.git_service.repo_path,
        intent_root=core_context.git_service.repo_path / ".intent",
    )
    key_path = core_context.git_service.repo_path / ".intent" / "keys" / "private.key"
    if key_path.exists() and not force:
        if not typer.confirm("⚠️ Key exists. Overwrite?"):
            raise typer.Exit(1)
    try:
        keygen(
            identity,
            path_resolver=path_resolver,
            file_handler=core_context.file_handler,
            allow_overwrite=force or key_path.exists(),
        )
    except KeyManagementError as exc:
        raise typer.Exit(exc.exit_code)
