#!/usr/bin/env python3
# scripts/list_unassigned.py
import asyncio
import re
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.database.session_manager import get_session
from shared.config import settings

console = Console()


async def list_unassigned_symbols():
    """
    Connects to the DB and lists all TRULY orphaned symbols.
    An orphan is a public symbol with no assigned capability key AND no incoming calls.
    """
    console.print(
        "[bold cyan]--- True Orphaned Symbol Report (Graph-Aware) ---[/bold cyan]"
    )
    try:
        async with get_session() as session:
            console.print("   -> Fetching full symbol and call graph from database...")
            stmt = text(
                """
                SELECT id, symbol_path, module, qualname, kind, is_public, key, calls
                FROM core.symbols
                ORDER BY module, symbol_path;
                """
            )
            result = await session.execute(stmt)
            all_symbols = [dict(row._mapping) for row in result]
            console.print(f"   -> Analyzing {len(all_symbols)} total symbols.")

            all_called_symbols = set()
            for symbol in all_symbols:
                called_list = symbol.get("calls") or []
                for called_qualname in called_list:
                    all_called_symbols.add(called_qualname)
            
            console.print(f"   -> Found {len(all_called_symbols)} unique symbol names that are being called.")

            orphaned_symbols = []
            for symbol in all_symbols:
                is_public = symbol.get("is_public", False)
                has_no_key = symbol.get("key") is None

                # --- START OF THE FINAL, CORRECT FIX ---
                # Check for both the full qualified name and the short name.
                qualname = symbol.get("qualname", "")
                short_name = qualname.split('.')[-1]
                is_called = (qualname in all_called_symbols) or (short_name in all_called_symbols)
                # --- END OF THE FINAL, CORRECT FIX ---

                if is_public and has_no_key and not is_called:
                    orphaned_symbols.append(symbol)
            

            if not orphaned_symbols:
                console.print(
                    "\n[bold green]✅ Success! No truly orphaned public symbols found.[/bold green]"
                )
                return

            console.print(
                f"\n[bold yellow]Found {len(orphaned_symbols)} true orphaned public symbols that require definition or removal:[/bold yellow]"
            )
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("File Path (Module)", style="cyan")
            table.add_column("Symbol Path", style="green")

            for symbol in orphaned_symbols:
                table.add_row(symbol["module"], symbol["symbol_path"])
            console.print(table)
    except Exception as e:
        console.print(f"\n[bold red]❌ An error occurred: {e}[/bold red]", extra_data={'exception': str(e)})


if __name__ == "__main__":
    asyncio.run(list_unassigned_symbols())