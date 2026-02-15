# src/body/cli/resources/symbols/__init__.py
"""Symbol registry and Knowledge Graph operations."""

from __future__ import annotations

# 2. Register all symbol neurons
from . import audit, fix_ids, resolve_duplicates, sync, tag

# 1. Import the stable app from the hub
from .hub import app


__all__ = ["app"]
