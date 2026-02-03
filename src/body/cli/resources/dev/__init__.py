# src/body/cli/resources/dev/__init__.py
"""Developer workflow and interaction operations."""

from __future__ import annotations

import typer


app = typer.Typer(
    name="dev",
    help="High-level developer workflows: synchronization, AI chat, and interactive tools.",
    no_args_is_help=True,
)

# Actions
from . import chat, sync, test


__all__ = ["app"]
