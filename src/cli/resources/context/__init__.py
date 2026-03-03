# src/cli/resources/context/__init__.py
"""
Context Resource - Context building and exploration.

Commands:
- build   : Agent simulation — exact context CoderAgent sees (uses build_for_task)
- explain : Semantic exploration — "what code relates to this concept?"
- search  : Direct pattern search (fast path, queries DB directly)
- cache   : Manage context cache
"""

from __future__ import annotations

# 2. Register all neurons (import triggers @app.command decorators)
from . import build, cache, explain, search

# 1. Import stable hub first
from .hub import app


__all__ = ["app"]
