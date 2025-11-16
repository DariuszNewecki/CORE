# src/body/cli/logic/tools.py
"""
Registers a 'tools' command group for powerful, operator-focused maintenance tasks.
This is the new, governed home for logic from standalone scripts.
"""

from __future__ import annotations

import typer
from features.maintenance.maintenance_service import rewire_imports
from rich.console import Console

console = Console()
tools_app = typer.Typer(
    help="Governed, operator-focused maintenance and refactoring tools."
)


@tools_app.command(
    "rewire-imports",
    help="Run after major refactoring to fix all Python import statements across 'src/'.",
)
# ID: 4d6a0245-20c9-425e-a0cd-a390c8dd063c
def rewire_imports_cli(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to the files."
    ),
):
    """
    CLI wrapper for the import rewiring service.
    """
    dry_run = not write
    console.print("🚀 Starting architectural import re-wiring script...")
    if dry_run:
        console.print("💧 [yellow]DRY RUN MODE[/yellow]: No files will be changed.")
    else:
        console.print("🟢 [bold green]WRITE MODE[/bold green]: Files will be modified.")

    total_changes = rewire_imports(dry_run=dry_run)

    console.print("\n--- Re-wiring Complete ---")
    if dry_run:
        console.print(
            f"💧 DRY RUN: Found {total_changes} potential import changes to make."
        )
        console.print("   Run with '--write' to apply them.")
    else:
        console.print(f"✅ APPLIED: Made {total_changes} import changes.")

    console.print("\n--- NEXT STEPS ---")
    console.print(
        "1.  VERIFY: Run 'make format' and then 'make check' to ensure compliance."
    )


# The obsolete register function has been removed.
