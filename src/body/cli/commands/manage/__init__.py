# src/body/cli/commands/manage/__init__.py
"""
Manage subcommands package.
Re-exports all departmental sub-apps for the main manage shell.
"""

from __future__ import annotations

from .database import db_sub_app
from .dotenv import dotenv_sub_app
from .keys import keys_sub_app
from .patterns import patterns_sub_app
from .policies import policies_sub_app
from .project import project_sub_app
from .proposals import proposals_sub_app
from .vectors import app as vectors_sub_app


__all__ = [
    "db_sub_app",
    "dotenv_sub_app",
    "keys_sub_app",
    "patterns_sub_app",
    "policies_sub_app",
    "project_sub_app",
    "proposals_sub_app",
    "vectors_sub_app",
]
