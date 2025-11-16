# src/body/cli/logic/symbol_drift.py
"""
Implements the `inspect symbol-drift` command, a diagnostic tool to detect
discrepancies between symbols on the filesystem and those in the database.
"""

from __future__ import annotations

import asyncio

from features.introspection.sync_service import SymbolScanner
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from services.database.session_manager import get_session
from sqlalchemy import text

console = Console()


async def _run_drift_analysis():
    """
    The core logic that scans source, queries the DB, and compares the results.
    """
    console.print("[bold cyan]🚀 Running Symbol Drift Analysis...[/bold cyan]")

    # 1. Scan the filesystem to get the ground truth
    console.print("   -> Scanning 'src/' directory for all public symbols...")
    scanner = SymbolScanner()
    code_symbols = await asyncio.to_thread(scanner.scan)
    code_symbol_paths = {s["symbol_path"] for s in code_symbols}
    console.print(f"      - Found {len(code_symbol_paths)} symbols in source code.")

    # 2. Query the database to get the current state
    console.print("   -> Querying database for all registered symbols...")
    db_symbol_paths = set()
    try:
        async with get_session() as session:
            result = await session.execute(text("SELECT symbol_path FROM core.symbols"))
            db_symbol_paths = {row[0] for row in result}
        console.print(f"      - Found {len(db_symbol_paths)} symbols in the database.")
    except Exception as e:
        console.print(f"[bold red]❌ Database query failed: {e}[/bold red]")
        console.print("   Please ensure your database is running and accessible.")
        return

    # 3. Compare the two sets to find the drift
    ghost_symbols_in_db = sorted(list(db_symbol_paths - code_symbol_paths))
    new_symbols_in_code = sorted(list(code_symbol_paths - db_symbol_paths))

    console.print("\n--- Analysis Complete ---")

    if not ghost_symbols_in_db and not new_symbols_in_code:
        console.print(
            Panel(
                "[bold green]✅ No drift detected.[/bold green]\nThe database is perfectly synchronized with the source code.",
                title="Result",
                border_style="green",
            )
        )
        return

    # Display findings
    if ghost_symbols_in_db:
        table = Table(
            title=f"👻 Found {len(ghost_symbols_in_db)} Ghost Symbols in Database",
            caption="These symbols exist in the DB but NOT in the source code. They should be pruned.",
            show_header=True,
            header_style="bold red",
        )
        table.add_column("Obsolete Symbol Path", style="red")
        for symbol in ghost_symbols_in_db:
            table.add_row(symbol)
        console.print(table)
        console.print(
            "\n[bold]Diagnosis:[/bold] The `sync-knowledge` command is failing to delete obsolete symbols from the database."
        )

    if new_symbols_in_code:
        table = Table(
            title=f"✨ Found {len(new_symbols_in_code)} New Symbols in Source Code",
            caption="These symbols exist in the code but NOT in the DB. They need to be synchronized.",
            show_header=True,
            header_style="bold green",
        )
        table.add_column("New Symbol Path", style="green")
        for symbol in new_symbols_in_code:
            table.add_row(symbol)
        console.print(table)

    console.print(
        "\n[bold]Next Step:[/bold] This report confirms a bug in the sync logic. Please proceed with fixing the `run_sync_with_db` function."
    )


# ID: 1342dd1f-2117-469d-b5a3-9e3379f68197
def inspect_symbol_drift():
    """Synchronous Typer wrapper for the async drift analysis logic."""
    asyncio.run(_run_drift_analysis())
