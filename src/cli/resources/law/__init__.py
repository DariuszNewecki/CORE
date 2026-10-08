# src/cli/resources/law/__init__.py
"""Law resource hub — the assistant surface's law answers (ADR-168 D4.3)."""

from __future__ import annotations

from . import commands
from .hub import app


__all__ = ["app"]
