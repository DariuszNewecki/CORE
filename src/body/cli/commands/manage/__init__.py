# src/body/cli/commands/manage/__init__.py
"""
Manage subcommands organized as separate modules.

Each subcommand (database, patterns, etc.) is defined in its own file
and registered with manage_app.
"""

from __future__ import annotations

# Import subcommand apps
from .patterns import patterns_sub_app
from .policies import policies_sub_app
from .vectors import app as vectors_sub_app


__all__ = [
    "patterns_sub_app",
    "policies_sub_app",
    "vectors_sub_app",
]
