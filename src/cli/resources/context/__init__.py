# src/body/cli/resources/context/__init__.py
"""
Context Resource - Natural language context building.

Commands:
- build: Build context from natural language query
- search: Direct pattern search (fast path)
- cache: Manage context cache
"""

from __future__ import annotations

import typer

from .build import build
from .cache import cache
from .search import search


app = typer.Typer(
    name="context",
    help="Build and manage context packages for LLM assistance.",
)

# Register commands
app.command()(build)
app.command()(search)
app.command()(cache)
