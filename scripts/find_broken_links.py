# scripts/find_broken_links.py
import asyncio
import sys
from pathlib import Path

# --- THIS IS THE FIX ---
# Add the project's 'src' directory to Python's path
# This allows the script to find modules like 'services' and 'shared'
project_root = Path(__file__).resolve().parents[1]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
# --- END OF FIX ---

from qdrant_client import AsyncQdrantClient
from rich.console import Console
from services.database.session_manager import get_session
from shared.config import settings
from sqlalchemy import text

console = Console()


async def find_broken_links():
    console.print(
        "[bold cyan]🔍 Finding broken links between PostgreSQL and Qdrant...[/bold cyan]"
    )
    broken_links = []
    try:
        # 1. Get all links from our database
        async with get_session() as session:
            result = await session.execute(
                text("SELECT symbol_id, vector_id FROM core.symbol_vector_links")
            )
            db_links = {str(row.symbol_id): str(row.vector_id) for row in result}

        if not db_links:
            console.print("[yellow]No vector links found in the database.[/yellow]")
            return

        # 2. Check if each of these IDs exists in Qdrant
        qdrant_client = AsyncQdrantClient(url=settings.QDRANT_URL)
        qdrant_ids_to_check = list(db_links.values())

        # Qdrant's retrieve lets us check many IDs at once
        records = await qdrant_client.retrieve(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            ids=qdrant_ids_to_check,
            with_payload=False,
            with_vectors=False,
        )

        found_qdrant_ids = {str(record.id) for record in records}

        # 3. Find the difference
        for symbol_id, vector_id in db_links.items():
            if vector_id not in found_qdrant_ids:
                broken_links.append({"symbol_id": symbol_id, "vector_id": vector_id})

    except Exception as e:
        console.print(f"[bold red]An error occurred: {e}[/bold red]")
        return

    if not broken_links:
        console.print(
            "[bold green]✅ No broken links found! Your data is consistent.[/bold green]"
        )
        return

    console.print(
        f"\n[bold red]❌ Found {len(broken_links)} broken link(s):[/bold red]"
    )
    console.print(
        "These symbols have a link in PostgreSQL, but the corresponding vector is missing from Qdrant."
    )

    # Prepare the SQL command for the user to fix the issue
    ids_to_delete = [link["symbol_id"] for link in broken_links]
    ids_sql_list = ", ".join([f"'{_id}'" for _id in ids_to_delete])
    delete_command = (
        f"DELETE FROM core.symbol_vector_links WHERE symbol_id IN ({ids_sql_list});"
    )

    console.print(
        "\n[bold]To fix this, run the following SQL command against your database:[/bold]"
    )
    console.print(f"[yellow]{delete_command}[/yellow]")
    console.print(
        "\nThen, run 'poetry run core-admin run vectorize --write' to regenerate the missing vectors."
    )


if __name__ == "__main__":
    asyncio.run(find_broken_links())
