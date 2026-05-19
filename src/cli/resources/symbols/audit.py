# src/cli/resources/symbols/audit.py
import typer
from rich.console import Console

from cli.logic.diagnostics import get_unassigned_symbols_logic
from cli.logic.symbol_drift import inspect_symbol_drift
from cli.utils import core_command

from .hub import app


console = Console()


@app.command("audit")
@core_command(dangerous=False, requires_context=True)
# ID: 2c32679a-ad9d-48e3-8cb0-b4cec7adea29
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
        "[bold cyan]🔍 1. Checking for Symbol Drift (Disk vs DB)...[/bold cyan]"
    )
    await inspect_symbol_drift()
    console.print("\n[bold cyan]🔍 2. Checking for Unassigned IDs...[/bold cyan]")
    unassigned = await get_unassigned_symbols_logic(core_context)
    if not unassigned:
        console.print("[green]✅ All public symbols have assigned IDs.[/green]")
    else:
        console.print(
            f"[yellow]⚠️  Found {len(unassigned)} symbols with no ID tag.[/yellow]"
        )
        for item in unassigned[:10]:
            console.print(f"   - {item.get('name')} ({item.get('file_path')})")
        if len(unassigned) > 10:
            console.print(f"   ... and {len(unassigned) - 10} more.")
        console.print(
            "\n[dim]Tip: Run 'core-admin symbols fix-ids --write' to fix this.[/dim]"
        )
