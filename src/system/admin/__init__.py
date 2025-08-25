# src/system/admin/__init__.py
"""
Intent: Modular CORE Admin CLI root. Wires subcommand groups (keys, proposals, guard)
without changing the public console script target (system.admin_cli:app).
"""

import typer

# All imports are now at the top of the file, before any other code.
from system.admin import agent as _agent
from system.admin import byor as _byor
from system.admin import develop as _develop
from system.admin import fixer as _fixer
from system.admin import guard as _guard
from system.admin import keys as _keys
from system.admin import migrator as _migrator
from system.admin import new as _new
from system.admin import proposals as _proposals  # <-- FIX: Corrected import
from system.admin import reviewer as _reviewer

app = typer.Typer(
    rich_markup_mode="markdown",
    help="""
    🏛️  **CORE Admin CLI**

    The command-line interface for the CORE Human Operator.
    Provides safe, governed commands for managing the system's constitution.
    """,
    no_args_is_help=True,
)

# Register command groups
_agent.register(app)
_keys.register(app)
_proposals.register(app)
_guard.register(app)
_migrator.register(app)
_fixer.register(app)
_byor.register(app)
_reviewer.register(app)
_new.register(app)
_develop.register(app)


__all__ = ["app"]
