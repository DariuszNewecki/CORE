# src/cli/commands/search.py
"""Registers the new, verb-based 'search' command group."""
from __future__ import annotations

import typer

from cli.logic.hub import hub_search
from cli.logic.knowledge_ops import search_knowledge_command

search_app = typer.Typer(
    help="Discover capabilities and commands.",
    no_args_is_help=True,
)

search_app.command("capabilities")(search_knowledge_command)
search_app.command("commands")(hub_search)


# ID: 8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e
def register(app: typer.Typer):
    """Register the 'search' command group to the main CLI app."""
    app.add_typer(search_app, name="search")
