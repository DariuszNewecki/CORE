# src/cli/resources/decisions/__init__.py
"""Decisions resource hub — the assistant surface's ADR answers (ADR-168 D4.3)."""

from __future__ import annotations

from . import commands
from .hub import app


__all__ = ["app"]
