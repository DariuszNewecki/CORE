# src/cli/commands/check.py
"""
Registers and implements the 'check' command group by composing
sub-groups for CI and diagnostic commands.
"""
from __future__ import annotations

import typer

from cli.commands.ci import ci_app
from cli.commands.diagnostics import diagnostics_app

check_app = typer.Typer(
    help="Read-only checks to validate constitutional and code health."
)

# Add the sub-groups
check_app.add_typer(ci_app, name="ci", help="High-level CI and system health checks.")
check_app.add_typer(
    diagnostics_app, name="diagnostics", help="Deep diagnostic and integrity checks."
)


# ID: 937c0f11-414e-46f3-b658-1c3debdae051
def register(app: typer.Typer) -> None:
    """Register the 'check' command group with the main CLI app."""
    app.add_typer(check_app, name="check")
