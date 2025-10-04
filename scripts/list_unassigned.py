#!/usr/bin/env python3
# scripts/list_unassigned.py
import asyncio
import sys
from pathlib import Path

import yaml
from rich.console import Console
from rich.table import Table
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.database.session_manager import get_session
from shared.config import settings

console = Console()

async def list_unassigned_symbols():
    """Connects to the DB and lists all symbols with a NULL key, respecting the ignore policy."""
    console.print("[bold cyan]--- Unassigned Symbol Report (Ignoring Boilerplate) ---[/bold cyan]")
    try:
        # --- THIS IS THE FIX: Load the ignore policy ---
        ignore_policy_path = settings.get_path("charter.policies.governance.audit_ignore_policy")
        ignore_policy = yaml.safe_load(ignore_policy_path.read_text("utf-8"))
        ignored_symbol_keys = {
            item["key"]
            for item in ignore_policy.get("symbol_ignores", [])
            if "key" in item
        }
        console.print(f"   -> Applying {len(ignored_symbol_keys)} ignore rules from the constitution.")
        # --- END OF FIX ---

        async with get_session() as session:
            stmt = text(
                """
                SELECT symbol_path, module AS file_path
                FROM core.symbols
                WHERE key IS NULL AND is_public = TRUE
                ORDER BY module, symbol_path;
                """
            )
            result = await session.execute(stmt)
            all_unassigned = [dict(row._mapping) for row in result]

            # --- THIS IS THE FIX: Filter the results ---
            unassigned = [
                s for s in all_unassigned if s["symbol_path"] not in ignored_symbol_keys
            ]
            # --- END OF FIX ---

            if not unassigned:
                console.print("\n[bold green]✅ Success! No unassigned public symbols found.[/bold green]")
                return

            console.print(f"\n[bold yellow]Found {len(unassigned)} unassigned public symbols that require definition:[/bold yellow]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("File Path (Module)", style="cyan")
            table.add_column("Symbol Path", style="green")

            for symbol in unassigned:
                table.add_row(symbol["file_path"], symbol["symbol_path"])
            console.print(table)
    except Exception as e:
        console.print(f"\n[bold red]❌ An error occurred: {e}[/bold red]")

if __name__ == "__main__":
    asyncio.run(list_unassigned_symbols())