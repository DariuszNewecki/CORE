# src/body/cli/logic/capability.py
"""
Provides the 'core-admin capability' command group for managing capabilities
in a constitutionally-aligned way. THIS MODULE IS NOW DEPRECATED and will be
removed after the DB-centric migration is complete.
"""

from __future__ import annotations

import logging

import typer

logger = logging.getLogger(__name__)

capability_app = typer.Typer(help="[DEPRECATED] Create and manage capabilities.")


@capability_app.command("new")
# ID: c2111920-a102-52e0-b8f5-1278411d4bae
def capability_new_deprecated():
    """[DEPRECATED] This command is now obsolete. Use 'knowledge sync' instead."""
    logger.warning("This command is deprecated and will be removed.")
    logger.info(
        "Please use 'poetry run core-admin knowledge sync' to synchronize symbols."
    )
