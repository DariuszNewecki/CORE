# src/cli/resources/lane/__init__.py
"""Assisted Remediation Lane — external-agent contract (ADR-109, issue #652)."""

from __future__ import annotations

import typer


app = typer.Typer(
    name="lane",
    help="Assisted Remediation Lane: work delegated findings under human-gated approval.",
    no_args_is_help=True,
)

from . import list as list_mod


app.command("list")(list_mod.list_delegated)

__all__ = ["app"]
