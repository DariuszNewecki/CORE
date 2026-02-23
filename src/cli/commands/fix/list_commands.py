# src/body/cli/commands/fix/list_commands.py
"""
Listing and discovery commands for the 'fix' CLI group.

Provides:
- core-admin fix list
"""

from __future__ import annotations

from rich.table import Table

from . import COMMAND_CONFIG, console, fix_app


@fix_app.command("list", help="List all available fix commands with their categories.")
# ID: 3a6c8ca8-b655-45dd-9dbf-1ca747fee287
def list_commands() -> None:
    """
    Render a Rich table of all fix subcommands based on COMMAND_CONFIG.

    Columns:
    - Command name
    - Category
    - Dangerous?
    - Confirmation?
    - Timeout (seconds)
    """
    table = Table(title="Available self-healing fix commands")

    table.add_column("Command", style="cyan", no_wrap=True)
    table.add_column("Category", style="magenta")
    table.add_column("Dangerous?", justify="center")
    table.add_column("Confirmation?", justify="center")
    table.add_column("Timeout (s)", justify="right")

    for name, cfg in sorted(COMMAND_CONFIG.items(), key=lambda item: item[0]):
        category = cfg.get("category", "-")
        dangerous = "yes" if cfg.get("dangerous", False) else "no"
        confirmation = "yes" if cfg.get("confirmation", False) else "no"
        timeout = str(cfg.get("timeout", "-"))

        table.add_row(name, category, dangerous, confirmation, timeout)

    console.print(table)
