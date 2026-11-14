# src/cli/resources/plugin/__init__.py
"""Plug-in commands: list installed plug-ins and check one (ADR-177)."""

from __future__ import annotations

import typer


app = typer.Typer(
    name="plugin",
    help="List installed plug-ins and check one against the plug-in contract.",
    no_args_is_help=True,
)


@app.callback()
# ID: c5a02c2c-1230-4e0c-bd78-5bd2d04bc9a7
def plugin() -> None:
    """List installed plug-ins and check one against the plug-in contract."""


from . import check, list_plugins  # registers the commands on `app`


__all__ = ["app"]
