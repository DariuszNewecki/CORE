# src/body/cli/resources/symbols/audit.py
import typer
from rich.console import Console

from body.cli.logic.diagnostics import get_unassigned_symbols_logic
from body.cli.logic.symbol_drift import inspect_symbol_drift
from shared.cli_utils import core_command

from .hub import app


console = Console()


@app.command("audit")
@core_command(dangerous=False, requires_context=True)
# ID: b067ce80-0d31-47fc-897a-4f4d2099e802
async def audit_symbols(ctx: typer.Context) -> None:
    """
    Audit symbol integrity and detect registry drift.

    Checks for:
    1. Symbols missing IDs (Anchors).
    2. Symbols in DB that no longer exist on disk (Ghosts).
    3. Symbols on disk not yet in DB (Drift).
    """
    core_context = ctx.obj

    console.print(
        "[bold cyan]\U0001f50d 1. Checking for Symbol Drift (Disk vs DB)...[/bold cyan]"
    )
    # Drift logic handles its own printing/logging
    await inspect_symbol_drift()

    console.print(
        "\n[bold cyan]\U0001f50d 2. Checking for Unassigned IDs...[/bold cyan]"
    )
    unassigned = await get_unassigned_symbols_logic(core_context)

    if not unassigned:
        console.print("[green]\u2705 All public symbols have assigned IDs.[/green]")
    else:
        console.print(
            f"[yellow]\u26a0\ufe0f  Found {len(unassigned)} symbols with no ID tag.[/yellow]"
        )
        for item in unassigned[:10]:
            console.print(f"   - {item.get('name')} ({item.get('file_path')})")
        if len(unassigned) > 10:
            console.print(f"   ... and {len(unassigned) - 10} more.")

        console.print(
            "\n[dim]Tip: Run 'core-admin symbols fix-ids --write' to fix this.[/dim]"
        )
