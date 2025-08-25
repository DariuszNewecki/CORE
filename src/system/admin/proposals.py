# src/system/admin/proposals.py
"""
Registers and defines the command-line interface for proposal lifecycle management.
This module serves as the public entry point for all proposal-related commands,
delegating the complex implementation logic to the `proposals_impl` module.
"""

from __future__ import annotations

import typer

# Import the implementation functions from the private helper module
from . import proposals_impl

# Create the Typer application for the "proposals" command group
proposals_app = typer.Typer(
    help="Work with constitutional proposals for governed changes."
)

# Register the implementation functions as CLI commands
proposals_app.command("list")(proposals_impl.proposals_list)
proposals_app.command("sign")(proposals_impl.proposals_sign)
proposals_app.command("approve")(proposals_impl.proposals_approve)


def register(app: typer.Typer) -> None:
    """
    Registers the 'proposals' command group with the main admin CLI application.

    Args:
        app: The main Typer application to which the command group will be added.
    """

    app.add_typer(proposals_app, name="proposals")
