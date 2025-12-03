# src/body/cli/commands/submit.py
"""
Registers the high-level 'submit' workflow command.
Refactored to use the Constitutional CLI Framework (@core_command).
"""

from __future__ import annotations

import typer
from features.project_lifecycle.integration_service import integrate_changes
from shared.cli_utils import core_command
from shared.context import CoreContext

submit_app = typer.Typer(
    help="High-level workflow commands for developers.",
    no_args_is_help=True,
)


@submit_app.command(
    "changes",
    help="The primary workflow to integrate staged code changes into the system.",
)
@core_command(dangerous=False)  # "submit" implies intent; no extra --write flag needed
# ID: 2bd6fcc9-9752-420a-a48e-35963a672ef0
async def integrate_command(
    ctx: typer.Context,
    commit_message: str = typer.Option(
        ..., "-m", "--message", help="The git commit message for this integration."
    ),
) -> None:
    """
    Orchestrates the full, autonomous integration of staged code changes.

    Runs:
    1. Policy Checks
    2. Tests
    3. Constitutional Audit
    4. Git Commit (if successful)
    """
    core_context: CoreContext = ctx.obj
    await integrate_changes(context=core_context, commit_message=commit_message)
