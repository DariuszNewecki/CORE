# src/body/cli/resources/constitution/__init__.py
"""Constitutional governance and policy operations."""

from __future__ import annotations

import typer


app = typer.Typer(
    name="constitution",
    help="Operations for the system mind: policies, schemas, and rule coverage.",
    no_args_is_help=True,
)

# Standard Verbs
from . import audit, query, status, validate


__all__ = ["app"]
