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
check_app.add_typer(ci_app, name="ci", help="High-level CI and system health checks.")
check_app.add_typer(
    diagnostics_app, name="diagnostics", help="Deep diagnostic and integrity checks."
)
