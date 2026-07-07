# src/cli/resources/project/__init__.py
"""Project lifecycle — operator commands only (consumer subset in core-cli)."""

from __future__ import annotations

import typer


app = typer.Typer(
    name="project",
    help="Operations for project lifecycle: scaffolding.",
    no_args_is_help=True,
)

from . import new


__all__ = ["app"]
