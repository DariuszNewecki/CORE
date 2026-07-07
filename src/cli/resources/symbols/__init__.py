# src/cli/resources/symbols/__init__.py
"""Symbol registry — operator commands only (consumer subset in core-cli)."""

from __future__ import annotations

from . import tag
from .hub import app


__all__ = ["app"]
