#!/usr/bin/env python3
# scripts/inspect_db_state.py
"""
A diagnostic script to directly inspect the state of the `core.symbols` table
to verify if refactoring changes are being correctly written and committed.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add the 'src' directory to the Python path to allow importing project modules
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

            # Check 1: Count total symbols
            total_result = await session.execute(
                text("SELECT COUNT(*) FROM core.symbols")
            )
            total_count = total_result.scalar_one()
            console.print(f"\n[bold]1. Total Symbols in Database:[/bold] {total_count}")

            # Check 2: Look for the specific symbol we deleted from the CLI layer
            status_symbol_path = "src/cli/logic/status.py::status"
            status_result = await session.execute(
                text("SELECT COUNT(*) FROM core.symbols WHERE symbol_path = :path"),
                {"path": status_symbol_path},
            )
            status_count = status_result.scalar_one()

            console.print(
                f"\n[bold]2. Checking for deleted symbol '{status_symbol_path}':[/bold]"
            )
            if status_count > 0:
                console.print(
                    f"   -> [bold red]FOUND {status_count} entr(y/ies).[/bold red] This symbol should have been deleted."
                )
            else:
                console.print(
                    "   -> [bold green]NOT FOUND.[/bold green] This is correct."
                )

            # Check 3: Look for the other duplicated symbol
            normalize_symbol_path = (
                "src/shared/utils/embedding_utils.py::normalize_text"
            )
            normalize_result = await session.execute(
                text("SELECT COUNT(*) FROM core.symbols WHERE symbol_path = :path"),
                {"path": normalize_symbol_path},
            )
            normalize_count = normalize_result.scalar_one()

            console.print(
                f"\n[bold]3. Checking for deleted symbol '{normalize_symbol_path}':[/bold]"
            )
            if normalize_count > 0:
                console.print(
                    f"   -> [bold red]FOUND {normalize_count} entr(y/ies).[/bold red] This symbol should have been deleted."
                )
            else:
                console.print(
                    "   -> [bold green]NOT FOUND.[/bold green] This is correct."
                )

            console.print(
                "\n[bold cyan]-------------------------------------[/bold cyan]"
            )

            # Final diagnosis
            if status_count > 0 or normalize_count > 0:
                console.print("\n[bold red]Diagnosis: CONFIRMED.[/bold red]")
                console.print(
                    "The database the application is using still contains the old, stale data. "
                    "This proves that the `sync-knowledge` command is updating a DIFFERENT database."
                )
                console.print(
                    "\n[bold]Next Step:[/bold] Check your `.env` and `docker-compose.yml` files. Ensure the `DATABASE_URL` is identical and correct everywhere, and that you do not have multiple database containers running."
                )
            else:
                console.print("\n[bold green]Diagnosis: UNEXPECTED.[/bold green]")
                console.print(
                    "The database appears to be correctly updated. The problem lies elsewhere, likely in the `inspect duplicates` command's logic itself."
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
