#!/usr/bin/env python3
# scripts/find_unvectorized_symbols.py
"""
A diagnostic script to find and list all symbols in the database that
have not been vectorized (i.e., their `vector_id` is NULL).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add the 'src' directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console
from rich.table import Table
from services.database.session_manager import get_session
from sqlalchemy import text

console = Console()


async def find_unvectorized():
    """Connects to the DB and lists all symbols where vector_id is NULL."""
    console.print("[bold cyan]--- Unvectorized Symbol Inspector ---[/bold cyan]")

    try:
        async with get_session() as session:
            console.print("✅ Successfully connected to the database.")

            stmt = text(
                """
                SELECT symbol_path, file_path, structural_hash
                FROM core.symbols
                WHERE vector_id IS NULL
                ORDER BY file_path, symbol_path;
                """
            )
            result = await session.execute(stmt)
            unvectorized_symbols = [dict(row._mapping) for row in result]

            if not unvectorized_symbols:
                console.print(
                    "\n[bold green]✅ Success! All symbols have been vectorized.[/bold green]"
                )
                return

            console.print(
                f"\n[bold red]Found {len(unvectorized_symbols)} symbols that are NOT vectorized:[/bold red]"
            )

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("File Path", style="cyan")
            table.add_column("Symbol Path", style="green")

            for symbol in unvectorized_symbols:
                table.add_row(symbol["file_path"], symbol["symbol_path"])

            console.print(table)

            console.print("\n[bold]Next Steps:[/bold]")
            console.print(
                "1. Review the list above for any patterns (e.g., specific directories, complex symbols)."
            )
            console.print(
                "2. Run `poetry run core-admin run vectorize --force --write` to attempt to fix them."
            )

    except Exception as e:
        console.print(
            "\n[bold red]❌ An error occurred while connecting to the database:[/bold red]"
        )
        console.print(str(e))


if __name__ == "__main__":
    asyncio.run(find_unvectorized())
