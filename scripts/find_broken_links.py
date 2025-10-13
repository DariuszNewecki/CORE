# scripts/find_broken_links.py
import asyncio
import sys
from pathlib import Path

# Add the project's 'src' directory to Python's path
# This allows the script to find modules like 'services' and 'shared'
project_root = Path(__file__).resolve().parents[1]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from qdrant_client import AsyncQdrantClient
from rich.console import Console
from services.database.session_manager import get_session
from shared.config import settings
from sqlalchemy import text

console = Console()


async def find_broken_links():
    """
    Finds and generates a fix for links in the database that point to
    non-existent vectors in Qdrant. This is the permanent diagnostic tool.
    """
    console.print(
        "[bold cyan]🔍 Finding broken links between PostgreSQL and Qdrant...[/bold cyan]"
    )

    try:
        # 1. Get all vector IDs that PostgreSQL thinks should exist in Qdrant.
        # The `symbol_id` is used as the point ID in Qdrant.
        async with get_session() as session:
            result = await session.execute(
                text("SELECT symbol_id FROM core.symbol_vector_links")
            )
            db_point_ids = {str(row.symbol_id) for row in result}

        if not db_point_ids:
            console.print("[yellow]No vector links found in the database.[/yellow]")
            return

        # 2. Get all point IDs that *actually* exist in Qdrant using the robust `scroll` method.
        qdrant_client = AsyncQdrantClient(url=settings.QDRANT_URL)
        qdrant_point_ids = set()
        offset = None
        while True:
            records, next_page_offset = await qdrant_client.scroll(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                limit=1000,  # Process in batches of 1000
                with_payload=False,
                with_vectors=False,
                offset=offset,
            )
            if not records:
                break

            qdrant_point_ids.update(str(record.id) for record in records)

            if next_page_offset is None:
                break
            offset = next_page_offset

        # 3. Find the difference: IDs that are in the DB but not in Qdrant.
        broken_point_ids = db_point_ids - qdrant_point_ids

    except Exception as e:
        console.print(f"[bold red]An error occurred during diagnosis: {e}[/bold red]")
        return

    if not broken_point_ids:
        console.print(
            "[bold green]✅ No broken links found! Your data is consistent.[/bold green]"
        )
        return

    console.print(
        f"\n[bold red]❌ Found {len(broken_point_ids)} broken link(s):[/bold red]"
    )
    console.print(
        "These symbols have a link in PostgreSQL, but the corresponding vector is missing from Qdrant."
    )

    # 4. Prepare the exact SQL command to fix the issue.
    ids_sql_list = ", ".join([f"'{_id}'" for _id in broken_point_ids])
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
