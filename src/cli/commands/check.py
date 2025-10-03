# src/cli/commands/check.py
"""Registers and implements the verb-based 'check' command group."""
from __future__ import annotations

import typer

from cli.logic.ci import audit, lint, test_system
from cli.logic.cli_utils import set_context as set_shared_context
from cli.logic.diagnostics import policy_coverage
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


# ID: 3c4d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f
def register(app: typer.Typer, context: CoreContext):
    """Register the 'check' command group to the main CLI app."""
    # Pass the context to the logic module.
    set_shared_context(context, "cli.logic.ci")
    app.add_typer(check_app, name="check")
