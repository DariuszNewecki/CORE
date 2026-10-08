# src/cli/resources/mcp/__init__.py
"""MCP resource hub — the assistant surface's MCP face (ADR-168 D4.3)."""

from __future__ import annotations

from . import run
from .hub import app


__all__ = ["app"]
