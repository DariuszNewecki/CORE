# src/system/admin/__init__.py
"""
Intent: Modular CORE Admin CLI root. Wires subcommand groups (keys, proposals, guard)
without changing the public console script target (system.admin_cli:app).
"""
from __future__ import annotations

import os
import sys

import typer

from shared.logger import configure_logging
from system.admin import agent as _agent
from system.admin import byor as _byor
from system.admin import fixer as _fixer
from system.admin import guard as _guard
from system.admin import keys as _keys

# from system.admin import migrator as _migrator
from system.admin import new as _new
from system.admin import proposals
from system.admin import reviewer as _reviewer

app = typer.Typer(
    help="""
    🏛️  CORE Admin CLI

    The command-line interface for the CORE Human Operator.
    Provides safe, governed commands for managing the system's constitution.
    """,
    no_args_is_help=True,
)


# Configure logging once per CLI invocation.
# - Defaults to WARNING for quietness.
# - -v → INFO, -vv → DEBUG
# - --quiet/-q → ERROR
# - JSON logs opt-in via env CORE_LOG_JSON=true (stderr only)
@app.callback()
def _configure_logging(
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        count=True,
        help="Increase verbosity (-v=INFO, -vv=DEBUG).",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Silence non-errors (ERROR level only).",
    ),
) -> None:
    if quiet:
        level = "ERROR"
    elif verbose >= 2:
        level = "DEBUG"
    elif verbose == 1:
        level = "INFO"
    else:
        level = "WARNING"

    json_mode = os.getenv("CORE_LOG_JSON", "false").lower() == "true"

    # IMPORTANT: log to the original stderr so Click/Typer's stdout capture is untouched.
    configure_logging(level=level, stream=sys.__stderr__, json_mode=json_mode)


# Register command groups
_agent.register(app)
_keys.register(app)
app.add_typer(proposals.proposals_app, name="proposals")
_guard.register(app)
# _migrator.register(app)
_fixer.register(app)
_byor.register(app)
_reviewer.register(app)
_new.register(app)

__all__ = ["app"]
