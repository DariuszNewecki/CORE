# src/body/cli/resources/code/__init__.py
"""Codebase resource commands."""

from __future__ import annotations

import typer


app = typer.Typer(
    name="code",
    help="Codebase quality, style, and verification operations.",
    no_args_is_help=True,
)

# Import command modules to register them on the app
from . import audit, docstrings, format, lint, logging, test


__all__ = ["app"]
