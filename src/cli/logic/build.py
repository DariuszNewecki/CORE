# src/cli/commands/build.py
"""
Registers and implements the 'build' command group for generating
artifacts from the database or constitution.
"""

from __future__ import annotations

import typer

# The old codegraph_builder is no longer a primary artifact.
# It's now implicitly run by 'knowledge sync'.
from features.introspection.generate_capability_docs import (
    main as generate_capability_docs,
)

build_app = typer.Typer(
    help="Commands to build artifacts (e.g., documentation) from the database."
)

build_app.command(
    "capability-docs",
    help="Generate the capability reference documentation from the DB.",
)(generate_capability_docs)


# ID: 2e170c82-210d-401c-a721-6f9d27239a6d
def register(app: typer.Typer) -> None:
    """Register the 'build' command group with the main CLI app."""
    app.add_typer(build_app, name="build")
