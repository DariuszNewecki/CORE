# src/system/admin/new.py
"""
Handles the 'core-admin new' command for creating new project scaffolds.
Intent: Defines the 'core-admin new' command, a user-facing wrapper
around the Scaffolder tool.
"""

from __future__ import annotations

import typer

from system.tools.scaffolder import new_project


# CAPABILITY: system.cli.register_command
def register(app: typer.Typer) -> None:
    """Register the 'new' command with the main CLI app."""
    # Directly register the imported new_project function under the name 'new'
    app.command("new")(new_project)
