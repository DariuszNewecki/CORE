# scripts/verify_live_config.py
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
from shared.config import settings
from sqlalchemy import text

console = Console()


async def inspect_live_database_config():
    """
    Connects to the database using the EXACT same method as the application
    and prints the live cognitive roles configuration it sees.
    """
    console.print(
        "[bold cyan]--- Live Application Configuration Inspector ---[/bold cyan]"
    )
    try:
        # Print the database URL the application is actually using
        console.print(
            "\n[bold]1. Database Connection String Used by Application:[/bold]"
        )
        console.print(f"[yellow]{settings.DATABASE_URL}[/yellow]")

        async with get_session() as session:
            console.print(
                "\n[bold]2. Live Data in 'core.cognitive_roles' Table (as seen by the app):[/bold]"
            )
            result = await session.execute(
                text("SELECT role, assigned_resource FROM core.cognitive_roles")
            )
            live_data = [dict(row._mapping) for row in result]

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("role")
            table.add_column("assigned_resource")
            for row in live_data:
                table.add_row(row["role"], row["assigned_resource"])
            console.print(table)

            # Final Diagnosis
            reviewer_role = next(
                (item for item in live_data if item["role"] == "CodeReviewer"), None
            )
            if reviewer_role and reviewer_role["assigned_resource"] == "ollama_local":
                console.print(
                    "\n[bold red]DIAGNOSIS:[/bold red] The application is connected to a database that still contains the OLD data."
                )
                console.print(
                    "This proves the application is NOT connecting to the same database as your pgAdmin/psql client."
                )
            elif (
                reviewer_role and reviewer_role["assigned_resource"] == "deepseek_chat"
            ):
                console.print(
                    "\n[bold green]DIAGNOSIS:[/bold green] The application IS seeing the correct data. The problem lies elsewhere."
                )
            else:
                console.print(
                    "\n[bold yellow]DIAGNOSIS:[/bold yellow] The 'CodeReviewer' role data is missing or unexpected."
                )

    except Exception as e:
        console.print(
            f"\n[bold red]❌ An error occurred while trying to connect or query: {e}[/bold red]"
        )
        console.print(
            "   This may indicate the DATABASE_URL points to a non-existent or inaccessible database."
        )


if __name__ == "__main__":
    asyncio.run(inspect_live_database_config())
