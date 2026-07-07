# src/cli/resources/code/__init__.py
"""Codebase resource hub — operator commands only (consumer subset in core-cli)."""

from __future__ import annotations

from . import audit, clarity, complexity, refactor
from .hub import app


__all__ = ["app"]
