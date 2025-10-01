#!/usr/bin/env python3
# scripts/inspect_db_state.py
"""
A diagnostic script to directly inspect the state of the `core.symbols` table
to verify if capability keys are being correctly written and committed.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add the 'src' directory to the Python path to allow importing project modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console
from sqlalchemy import text

from services.database.session_manager import get_session

console = Console()


async def inspect_database_state():
    """Connects to the DB and reports on the state of the symbols table."""
    console.print("[bold cyan]--- CORE Database State Inspector ---[/bold cyan]")

    try:
        async with get_session() as session:
            console.print("✅ Successfully connected to the database.")

            # Check 1: Count total symbols
            total_result = await session.execute(text("SELECT COUNT(*) FROM core.symbols"))
            total_count = total_result.scalar_one()
            console.print(f"\n[bold]1. Total Symbols Found:[/bold] {total_count}")

            # Check 2: Count symbols WITH a defined key
            defined_result = await session.execute(
                text("SELECT COUNT(*) FROM core.symbols WHERE key IS NOT NULL")
            )
            defined_count = defined_result.scalar_one()
            console.print(f"[bold]2. Symbols WITH a capability key:[/bold] [bold green]{defined_count}[/bold green]")

            # Check 3: Count symbols WITHOUT a defined key
            undefined_result = await session.execute(
                text("SELECT COUNT(*) FROM core.symbols WHERE key IS NULL")
            )
            undefined_count = undefined_result.scalar_one()
            console.print(f"[bold]3. Symbols WITHOUT a capability key:[/bold] [bold red]{undefined_count}[/bold red]")

            # Check 4: Show a sample of defined keys
            if defined_count > 0:
                console.print("\n[bold]Sample of defined capability keys:[/bold]")
                sample_result = await session.execute(
                    text("SELECT symbol_path, key FROM core.symbols WHERE key IS NOT NULL LIMIT 5")
                )
                for row in sample_result:
                    console.print(f"  - [cyan]{row.key}[/cyan] -> {row.symbol_path}")
            
            console.print("\n[bold cyan]-------------------------------------[/bold cyan]")
            
            # Final diagnosis
            if defined_count > 0:
                console.print("\n[bold green]Diagnosis: SUCCESS.[/bold green]")
                console.print("The database IS being populated with capability keys. The problem likely lies within the 'sync-manifest' command.")
            else:
                console.print("\n[bold red]Diagnosis: FAILURE.[/bold red]")
                console.print("The database IS NOT being populated with capability keys. The problem lies within the 'define-symbols' command's database transaction.")

    except Exception as e:
        console.print(f"\n[bold red]❌ An error occurred while connecting to the database:[/bold red]")
        console.print(str(e))
        console.print("\nPlease ensure your DATABASE_URL in .env is correct and the database is running.")


if __name__ == "__main__":
    asyncio.run(inspect_database_state())