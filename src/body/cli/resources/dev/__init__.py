# src/body/cli/resources/dev/__init__.py
"""Developer workflow and interaction operations."""

from __future__ import annotations

# 2. Register all sub-modules (neurons)
from . import chat, stability, sync, test

# 1. Import the centralized app from the hub (prevents circular errors)
from .hub import app


__all__ = ["app"]
