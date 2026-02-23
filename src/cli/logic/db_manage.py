# src/body/cli/logic/db_manage.py
"""Provides functionality for the db_manage module."""

from __future__ import annotations

import typer

from .db import app as db_app
from .db import app as knowledge_db_app


# Top-level Typer app exposed by this module
app = typer.Typer(help="Database management meta-commands")

# Mount groups
app.add_typer(db_app, name="db")

knowledge_app = typer.Typer(help="Knowledge operations")
knowledge_app.add_typer(knowledge_db_app, name="db")
app.add_typer(knowledge_app, name="knowledge")

__all__ = ["app"]
