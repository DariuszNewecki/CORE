# src/system/admin/new.py
"""
Handles the 'core-admin new' command for creating new project scaffolds.
Intent: Defines the 'core-admin new' command, a user-facing wrapper
around the Scaffolder tool.
"""

from __future__ import annotations

import typer

from features.project_lifecycle.scaffolding_service import new_project


# ID: aef6ac5d-843a-47f3-b5df-dd7d0aea3621
def register(app: typer.Typer) -> None:
    """Register the 'new' command with the main CLI app."""
    # Directly register the imported new_project function under the name 'new'
    app.command("new")(new_project)
