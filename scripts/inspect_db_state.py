# scripts/inspect_db_state.py
"""
A diagnostic script to directly inspect the state of the `core.symbols` table
to verify if the 'define-symbols' command is successfully updating records.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add the 'src' directory to the Python path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console
from services.database.session_manager import get_session
from sqlalchemy import text

console = Console()


async def inspect_database_state():
    """Connects to the DB and reports on the state of key symbols."""
    console.print("[bold cyan]--- CORE Database State Inspector ---[/bold cyan]")

    try:
        async with get_session() as session:
            console.print("✅ Successfully connected to the database.")

            # Check for a specific symbol that should have been defined.
            # We'll check for 'resolve_duplicate_ids' which was in your successful `define-symbols` run logs.
            symbol_path_to_check = "src/features/self_healing/duplicate_id_service.py::resolve_duplicate_ids"
            
            result = await session.execute(
                text("SELECT key FROM core.symbols WHERE symbol_path = :path"),
                {"path": symbol_path_to_check},
            )
            # Use scalar_one_or_none() which returns the value, or None if no row is found.
            symbol_key = result.scalar_one_or_none()

            console.print(
                f"\n[bold]Checking for symbol '{symbol_path_to_check}':[/bold]"
            )
            
            # This logic now correctly handles all cases
            if symbol_key is None:
                 console.print(
                    f"   -> [bold red]FOUND, BUT KEY IS NULL.[/bold red] This symbol was NOT updated by the 'define-symbols' command."
                )
            else:
                 console.print(
                    f"   -> [bold green]FOUND AND DEFINED![/bold green] Key is '{symbol_key}'. This is unexpected based on the audit."
                )

            console.print(
                "\n[bold cyan]-------------------------------------[/bold cyan]"
            )

            # Final diagnosis
            if symbol_key is None:
                console.print("\n[bold red]Diagnosis: CONFIRMED.[/bold red]")
                console.print(
                    "The database the application is connecting to still contains the OLD, undefined data."
                )
                console.print(
                    "This proves that the `define-symbols` command is writing its changes to a DIFFERENT database."
                )
                console.print(
                    "\n[bold]Next Step:[/bold] Check your `.env` and `docker-compose.yml` files. Ensure the `DATABASE_URL` is identical and correct everywhere, and that you do not have multiple database containers running."
                )
            else:
                console.print("\n[bold green]Diagnosis: UNEXPECTED.[/bold green]")
                console.print(
                    "The database appears to be correctly updated. The problem may lie elsewhere."
                )

    except Exception as e:
        console.print(
            "\n[bold red]❌ An error occurred while connecting to the database:[/bold red]"
        )
        console.print(str(e))
        console.print(
            "\nPlease ensure your DATABASE_URL in .env is correct and the database is running."
        )


if __name__ == "__main__":
    asyncio.run(inspect_database_state())