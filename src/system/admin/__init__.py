# src/system/admin/__init__.py
"""
Intent: Modular CORE Admin CLI root. Wires subcommand groups (keys, proposals, guard)
without changing the public console script target (system.admin_cli:app).
"""

import typer

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
from system.admin import keys as _keys  # noqa: E402
from system.admin import proposals as _proposals  # noqa: E402
from system.admin import guard as _guard  # noqa: E402
from system.admin import migrator as _migrator # noqa: E402
from system.admin import fixer as _fixer # noqa: E402
from system.admin import byor as _byor # noqa: E402
from system.admin import scaffolder as _scaffolder # noqa: E402

_keys.register(app)
_proposals.register(app)
_guard.register(app)
_migrator.register(app)
_fixer.register(app)
_byor.register(app)
_scaffolder.register(app)


__all__ = ["app"]
