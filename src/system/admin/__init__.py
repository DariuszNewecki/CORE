# src/system/admin/__init__.py
"""
Intent: Modular CORE Admin CLI root. Wires subcommand groups (keys, proposals, guard)
without changing the public console script target (system.admin_cli:app).
"""

import typer
from rich.console import Console

# All imports are now at the top of the file, before any other code.
from system.admin import agent as _agent
from system.admin import byor as _byor
from system.admin import chat as _chat
from system.admin import develop as _develop
from system.admin import fixer as _fixer
from system.admin import guard as _guard
from system.admin import interactive as _interactive
from system.admin import keys as _keys
from system.admin import migrator as _migrator
from system.admin import new as _new
from system.admin import proposals as _proposals
from system.admin import reviewer as _reviewer
from system.admin import system as _system

console = Console()

app = typer.Typer(
    rich_markup_mode="markdown",
    help="""
    :house:  **CORE Admin CLI** - The interface for the Human Operator.

    Use commands directly or run without arguments for an interactive menu.
    """,
    # --- THIS IS THE CRITICAL FIX ---
    # This tells Typer to run our callback function even if no subcommand is given.
    invoke_without_command=True,
    # --- END OF FIX ---
    no_args_is_help=False,  # We are now handling the "no args" case ourselves
    rich_help_panel="Commands",
)


@app.callback()
def main(ctx: typer.Context):
    """
    Main callback. If no command is specified, launches the interactive menu.
    """
    if ctx.invoked_subcommand is None:
        console.print(
            "[bold green]No command specified. Launching interactive menu...[/bold green]"
        )
        _interactive.launch_interactive_menu()
        raise typer.Exit()


# Register command groups
_system.register(app)
_fixer.register(app)
_proposals.register(app)
_agent.register(app)
_reviewer.register(app)
_new.register(app)
_byor.register(app)
_develop.register(app)
_chat.register(app)
_keys.register(app)
_migrator.register(app)
_guard.register(app)


__all__ = ["app"]
