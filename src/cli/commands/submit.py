# src/cli/commands/submit.py
"""
Registers the new, high-level 'submit' workflow command.
"""

from __future__ import annotations

import asyncio

import typer

from features.project_lifecycle.integration_service import integrate_changes
from shared.context import CoreContext

submit_app = typer.Typer(
    help="High-level workflow commands for developers.",
    no_args_is_help=True,
)

_context: CoreContext | None = None


@submit_app.command(
    "changes",
    help="The primary workflow to integrate staged code changes into the system.",
)
# ID: 2d1e8a9f-7b6c-4d5e-8f9a-0b1c2d3e4f5a
def integrate_command(
    ctx: typer.Context,
    commit_message: str = typer.Option(
        ..., "-m", "--message", help="The git commit message for this integration."
    ),
):
    """Orchestrates the full, autonomous integration of staged code changes."""
    core_context: CoreContext = ctx.obj
    asyncio.run(integrate_changes(context=core_context, commit_message=commit_message))
