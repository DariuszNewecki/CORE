# src/body/cli/commands/fix/__init__.py
"""
Registers the 'fix' command group and its associated self-healing capabilities.

This module acts as a pure registration hub for the CLI.
Logic and UI helpers have been moved to prevent circular imports
between the CLI and the Atomic Body layers.

LEGACY ELIMINATION:
- Removed 'line-lengths' per Roadmap.
- Removed internal UI helpers to break circular dependencies.
"""

from __future__ import annotations

import typer
from rich.console import Console

from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()

# Configuration mapping for CLI metadata
COMMAND_CONFIG = {
    "code-style": {"category": "formatting", "dangerous": False},
    "headers": {"category": "compliance", "dangerous": True},
    "docstrings": {"category": "documentation", "dangerous": True},
    "clarity": {"category": "refactoring", "dangerous": True},
    "complexity": {"category": "refactoring", "dangerous": True},
    "ids": {"category": "metadata", "dangerous": True},
    "purge-legacy-tags": {"category": "cleanup", "dangerous": True},
    "policy-ids": {"category": "metadata", "dangerous": True},
    "tags": {"category": "metadata", "dangerous": True},
    "db-registry": {"category": "database", "dangerous": False},
    "duplicate-ids": {"category": "metadata", "dangerous": True},
    "vector-sync": {"category": "database", "dangerous": True},
    "atomic-actions": {"category": "compliance", "dangerous": True},
    "body-ui": {"category": "governance", "dangerous": True},
    "imports": {"category": "formatting", "dangerous": False},
}

fix_app = typer.Typer(
    help="Self-healing tools that write changes to the codebase.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@fix_app.callback()
# ID: 4165545f-18b7-4890-b89f-605ae2772b16
def fix_callback(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug output"),
):
    """Self-healing tools organized by category."""
    if debug:
        settings.DEBUG = True
    if verbose:
        settings.VERBOSE = True


# LATE IMPORTS: These register themselves on fix_app when imported.
# This must remain at the bottom to ensure fix_app is defined first.
import body.cli.commands.fix.all_commands
import body.cli.commands.fix.apply_providers
import body.cli.commands.fix.atomic_actions
import body.cli.commands.fix.body_ui
import body.cli.commands.fix.clarity
import body.cli.commands.fix.code_style
import body.cli.commands.fix.db_tools
import body.cli.commands.fix.docstrings
import body.cli.commands.fix.fix_ir
import body.cli.commands.fix.handler_discovery
import body.cli.commands.fix.imports
import body.cli.commands.fix.list_commands
import body.cli.commands.fix.metadata
import body.cli.commands.fix.modularity
import body.cli.commands.fix.provider_refactor
import body.cli.commands.fix.settings_access
