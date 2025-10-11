# scripts/inspect_runtime_settings.py
"""
A diagnostic script to inspect the contents of the core.runtime_settings table.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add the 'src' directory to Python's path to allow imports
project_root = Path(__file__).resolve().parents[1]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from rich.console import Console
from rich.table import Table
from services.database.session_manager import get_session
from sqlalchemy import text

console = Console()


async def inspect_runtime_settings():
    """Connects to the DB and prints the contents of the runtime_settings table."""
    console.print(
        "[bold cyan]--- Live Runtime Settings Inspector (from Database) ---[/bold cyan]"
    )

    try:
        async with get_session() as session:
            console.print("✅ Successfully connected to the database.")

            stmt = text(
                "SELECT key, value, description, is_secret FROM core.runtime_settings ORDER BY key"
            )
            result = await session.execute(stmt)
            settings_data = [dict(row._mapping) for row in result]

            if not settings_data:
                console.print(
                    "[bold red]❌ The core.runtime_settings table is empty![/bold red]"
                )
                return

            console.print(
                f"\n[bold green]Found {len(settings_data)} settings in the database:[/bold green]"
            )

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Setting Key", style="cyan")
            table.add_column("Live Value", style="green")
            table.add_column("Is Secret?", style="red")
            table.add_column("Description")

            for setting in settings_data:
                # Mask secret values for security
                display_value = "********" if setting["is_secret"] else setting["value"]
                table.add_row(
                    setting["key"],
                    display_value,
                    str(setting["is_secret"]),
                    setting["description"] or "",
                )

            console.print(table)

    except Exception as e:
        console.print(
            "\n[bold red]❌ An error occurred while connecting to the database:[/bold red]"
        )
        console.print(str(e))
        console.print(
            "   Please ensure your DATABASE_URL in .env is correct and the database is running."
        )


if __name__ == "__main__":
    asyncio.run(inspect_runtime_settings())
