# src/cli/resources/dev/__init__.py

"""Developer workflow and interaction operations."""

from __future__ import annotations

# Register all sub-modules (neurons) — import order triggers @app.command decorators
from . import (
    campaign_review,
    refactor,
    smell_test,
    stability,
    strategic_audit,
    sync,
    test,
)

# Import the centralized app from the hub
from .hub import app


__all__ = ["app"]
