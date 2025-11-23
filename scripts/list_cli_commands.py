# scripts/list_cli_commands.py
"""
A simple, read-only diagnostic script to list all registered CLI commands
directly from the database.
"""

import asyncio
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table
from sqlalchemy import text

# Add project root to path to allow imports from src/
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))

from services.database.session_manager import get_session


async def list_commands():
    """Connects to the DB and prints the contents of the cli_commands table."""
    console = Console()
    console.print(
        "[bold cyan]--- Registered CLI Commands (from Database) ---[/bold cyan]"
    )

    try:
        async with get_session() as session:
            stmt = text(
                "SELECT name, category, summary FROM core.cli_commands ORDER BY name"
            )
            result = await session.execute(stmt)
            commands = [dict(row._mapping) for row in result]

        if not commands:
            console.print(
                "[bold red]❌ The core.cli_commands table is empty![/bold red]"
            )
            console.print(
                "   -> Please run `poetry run core-admin manage database sync-knowledge --write` to populate it."
            )
            return

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Command Name", style="cyan")
        table.add_column("Category", style="yellow")
        table.add_column("Summary")

        for command in commands:
            table.add_row(
                command.get("name"),
                command.get("category"),
                command.get("summary") or "No description.",
            )

        console.print(table)
        console.print(f"\n[bold green]✅ Found {len(commands)} commands.[/bold green]")

    except Exception as e:
        console.print(
            "\n[bold red]❌ An error occurred while querying the database:[/bold red]"
        )
        console.print(str(e))


if __name__ == "__main__":
    asyncio.run(list_commands())
