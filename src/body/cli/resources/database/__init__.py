# src/body/cli/resources/database/__init__.py
"""Database resource hub."""

from __future__ import annotations

# 2. Register all database neurons
from . import cleanup, export, migrate, status, sync, sync_registry

# 1. Import the stable app from the hub
from .hub import app


__all__ = ["app"]
