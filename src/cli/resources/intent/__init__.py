# src/cli/resources/intent/__init__.py
"""Intent resource hub."""

from __future__ import annotations

# Register all neurons
from . import sync_vocabulary
from .hub import app


__all__ = ["app"]
