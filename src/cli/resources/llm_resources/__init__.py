# src/cli/resources/llm_resources/__init__.py
"""llm-resources resource hub (#821 Unit 3)."""

from __future__ import annotations

# Register all neurons
from . import author
from .hub import app


__all__ = ["app"]
