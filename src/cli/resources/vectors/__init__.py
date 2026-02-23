# src/body/cli/resources/vectors/__init__.py
"""Vector resource hub."""

from __future__ import annotations

# Register all neurons
from . import cleanup, query, rebuild, status, sync, sync_code
from .hub import app


__all__ = ["app"]
