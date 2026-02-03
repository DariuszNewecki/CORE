# src/body/cli/resources/vectors/__init__.py
# ID: cli.resources.vectors
"""
Vector resource commands.

Constitutional Alignment:
- Resource: vectors (Qdrant vector store management)
- Actions: sync, query, rebuild, status, cleanup
- No layer exposure, resource-first pattern

Commands:
    core-admin vectors sync      - Sync documents to collections
    core-admin vectors query     - Semantic search
    core-admin vectors rebuild   - Rebuild collections from scratch
    core-admin vectors status    - Show health metrics
    core-admin vectors cleanup   - Remove orphaned vectors
"""

from __future__ import annotations

import typer


app = typer.Typer(
    name="vectors",
    help="Vector store operations (Qdrant)",
    no_args_is_help=True,
)

# Register command modules
from . import cleanup, query, rebuild, status, sync


__all__ = ["app"]
