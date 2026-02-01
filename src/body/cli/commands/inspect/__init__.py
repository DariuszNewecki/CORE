# src/body/cli/commands/inspect/__init__.py
# ID: body.cli.commands.inspect

"""
Modular inspect command group.

Constitutional Refactoring (Feb 2026):
- Split 800 LOC monolith into focused modules
- Each module <250 LOC (constitutional sweet spot)
- Clear separation of concerns
- Consolidated duplicate inspect_*.py files

Structure:
- status.py          - Database/system status
- decisions.py       - Decision trace inspection
- patterns.py        - Pattern classification analysis
- refusals.py        - Constitutional refusal tracking
- drift.py           - Symbol/vector/guard drift detection
- analysis.py        - Clusters, duplicates, common-knowledge
- diagnostics.py     - Command-tree, test-targets
- _helpers.py        - Shared helper functions
"""

from __future__ import annotations

import typer

from .analysis import analysis_commands
from .decisions import decisions_commands
from .diagnostics import diagnostics_commands
from .drift import drift_commands, register_drift_commands
from .patterns import patterns_commands
from .refusals import refusals_commands
from .status import status_commands


# Main inspect app
inspect_app = typer.Typer(
    help="Read-only commands to inspect system state and configuration.",
    no_args_is_help=True,
)

# Mount all subcommand groups
# Status and system
for cmd in status_commands:
    inspect_app.command(cmd["name"], **cmd.get("kwargs", {}))(cmd["func"])

# Decision traces
for cmd in decisions_commands:
    inspect_app.command(cmd["name"], **cmd.get("kwargs", {}))(cmd["func"])

# Pattern analysis
for cmd in patterns_commands:
    inspect_app.command(cmd["name"], **cmd.get("kwargs", {}))(cmd["func"])

# Constitutional refusals
for cmd in refusals_commands:
    inspect_app.command(cmd["name"], **cmd.get("kwargs", {}))(cmd["func"])

# Drift detection (includes guard commands)
for cmd in drift_commands:
    inspect_app.command(cmd["name"], **cmd.get("kwargs", {}))(cmd["func"])
register_drift_commands(inspect_app)  # Register guard commands

# Analysis tools
for cmd in analysis_commands:
    inspect_app.command(cmd["name"], **cmd.get("kwargs", {}))(cmd["func"])

# Diagnostics
for cmd in diagnostics_commands:
    inspect_app.command(cmd["name"], **cmd.get("kwargs", {}))(cmd["func"])


# Export for backward compatibility
__all__ = ["inspect_app"]
