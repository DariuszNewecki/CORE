# src/cli/resources/vectors/__init__.py
"""Vector resource hub — installation maintenance (operator surface).

`vectors query` stays in core-cli: it searches the governed repository.
"""

from __future__ import annotations

from . import cleanup, rebuild, status
from .hub import app


__all__ = ["app"]
