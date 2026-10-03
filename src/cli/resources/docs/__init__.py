# src/cli/resources/docs/__init__.py
"""Reader-facing documentation derived from live sources."""

from __future__ import annotations

import typer


app = typer.Typer(
    name="docs",
    help="Reader-facing documentation generated from live sources (the CLI trees).",
    no_args_is_help=True,
)

from . import generate


__all__ = ["app"]
