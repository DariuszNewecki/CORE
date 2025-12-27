# src/body/cli/logic/build.py
"""
Registers and implements the 'build' command group for generating
artifacts from the database or constitution.
"""

from __future__ import annotations

import typer

from features.introspection.generate_capability_docs import (
    main as generate_capability_docs_impl,
)
from shared.infrastructure.database.session_manager import get_session


build_app = typer.Typer(
    help="Commands to build artifacts (e.g., documentation) from the database."
)


@build_app.command("capability-docs")
# ID: 361a766b-e26f-4271-b43e-99967689a7c5
async def generate_capability_docs():
    """Generate the capability reference documentation from the DB."""
    async with get_session() as session:
        await generate_capability_docs_impl(session)
