# src/cli/resources/code/__init__.py
"""Codebase resource hub."""

from __future__ import annotations

# 2. Import modules RELATIVELY to trigger the @app.command registrations
# We don't need to assign these to variables; the import itself runs the decorators
from . import (
    actions,
    audit,
    audit_duplicates,
    check_imports,
    check_ui,
    clarity,
    complexity,
    docstrings,
    fix_atomic,
    format,
    integrity,
    lint,
    logging,
    refactor,
    test,
)

# 1. Import the 'app' from hub so it's available for admin_cli.py
from .hub import app


# 3. Export the app object
__all__ = ["app"]
