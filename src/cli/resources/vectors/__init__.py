# src/cli/resources/vectors/__init__.py
"""Vector resource hub — operator commands only (consumer subset in core-cli)."""

from __future__ import annotations

from . import cleanup
from .hub import app


__all__ = ["app"]
