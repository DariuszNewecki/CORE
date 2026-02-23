# src/body/cli/commands/coverage/__init__.py
"""Coverage management commands - modular architecture."""

from __future__ import annotations

import typer

from .analysis_commands import register_analysis_commands
from .check_commands import register_check_commands
from .generation_commands import register_generation_commands


coverage_app = typer.Typer(
    help="Test coverage management and autonomous remediation.", no_args_is_help=True
)

# Register command groups
register_check_commands(coverage_app)
register_generation_commands(coverage_app)
register_analysis_commands(coverage_app)

__all__ = ["coverage_app"]
