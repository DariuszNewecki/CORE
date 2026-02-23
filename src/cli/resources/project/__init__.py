# src/body/cli/resources/project/__init__.py
"""Project lifecycle and onboarding operations."""

from __future__ import annotations

import typer


app = typer.Typer(
    name="project",
    help="Operations for project lifecycle: scaffolding, onboarding, and documentation.",
    no_args_is_help=True,
)

# Standard Verbs
from . import docs, new, onboard


__all__ = ["app"]
