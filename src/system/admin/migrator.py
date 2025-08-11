# src/system/admin/migrator.py
"""
Intent: Registers the manifest migration tool with the CORE Admin CLI.
"""

import typer
from system.tools.manifest_migrator import migrate_manifest

def register(app: typer.Typer) -> None:
    """Register migration commands (manifest-migrator) under the admin CLI."""
    """Intent: Register migration commands under the admin CLI."""
    app.command("manifest-migrator")(migrate_manifest)