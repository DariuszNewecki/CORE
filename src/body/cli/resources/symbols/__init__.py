# src/body/cli/resources/symbols/__init__.py
"""Symbol registry and Knowledge Graph operations."""

from __future__ import annotations

import typer


app = typer.Typer(
    name="symbols",
    help="Operations for the symbol registry and Knowledge Graph identification.",
    no_args_is_help=True,
)

# Actions following standard verbs
from . import audit, fix_ids, sync


__all__ = ["app"]
