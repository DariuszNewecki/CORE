#!/usr/bin/env python3
# scripts/list_unassigned.py
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console
from rich.table import Table
from sqlalchemy import text

from services.database.session_manager import get_session

console = Console()

async def list_unassigned_symbols():
    """Connects to the DB and lists all symbols with a NULL key."""
    console.print("[bold cyan]--- Unassigned Symbol Report ---[/bold cyan]")
    try:
        async with get_session() as session:
            stmt = text(
                """
                SELECT symbol_path, file_path
                FROM core.symbols
                WHERE key IS NULL AND is_public = TRUE
                ORDER BY file_path, symbol_path;
                """
            )
            result = await session.execute(stmt)
            unassigned = [dict(row._mapping) for row in result]

            if not unassigned:
                console.print("\n[bold green]✅ Success! No unassigned public symbols found.[/bold green]")
                return

            console.print(f"\n[bold red]Found {len(unassigned)} unassigned public symbols:[/bold red]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("File Path", style="cyan")
            table.add_column("Symbol Path", style="green")

            for symbol in unassigned:
                table.add_row(symbol["file_path"], symbol["symbol_path"])
            console.print(table)
    except Exception as e:
        console.print(f"\n[bold red]❌ An error occurred: {e}[/bold red]")

if __name__ == "__main__":
    asyncio.run(list_unassigned_symbols())