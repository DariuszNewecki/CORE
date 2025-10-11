# src/cli/commands/check.py
"""Registers and implements the verb-based 'check' command group."""

from __future__ import annotations

import asyncio

import typer
from cli.logic.audit import audit, lint, test_system
from cli.logic.cli_utils import set_context as set_shared_context
from cli.logic.diagnostics import policy_coverage
from features.project_lifecycle.integration_service import check_integration_health
from shared.context import CoreContext

check_app = typer.Typer(
    help="Read-only validation and health checks.",
    no_args_is_help=True,
)

# Register the logic functions as commands
check_app.command("audit", help="Run the full constitutional self-audit.")(audit)
check_app.command("lint", help="Check code formatting and quality.")(lint)
check_app.command("tests", help="Run the pytest suite.")(test_system)
check_app.command("diagnostics", help="Audit the constitution for policy coverage.")(
    policy_coverage
)


# ID: 412e2478-00ea-4d54-a051-90b9f826c120
def register(app: typer.Typer, context: CoreContext):
    """Register the 'check' command group to the main CLI app."""

    @check_app.command(
        "system",
        help="Run the full developer sync & audit sequence (non-destructive).",
    )
    # ID: d455ad07-870d-442a-8f56-a9dadaecc441
    def system_check_command(ctx: typer.Context):
        """
        Runs the full integration health check without committing or rolling back.
        This is the primary developer command to check if work is ready to commit.
        """
        core_context: CoreContext = ctx.obj
        success = asyncio.run(check_integration_health(context=core_context))
        if not success:
            raise typer.Exit(code=1)

    # Pass the context to the other logic module that needs it.
    set_shared_context(context, "cli.logic.audit")
    app.add_typer(check_app, name="check")
