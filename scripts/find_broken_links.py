# scripts/find_broken_links.py
import asyncio
import sys
from pathlib import Path

# Add the project's 'src' directory to Python's path
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


async def list_postgres_vector_ids():
    """Connects ONLY to PostgreSQL and prints all vector_ids from the link table."""
    console.print(
        "\n[bold cyan]--- Querying PostgreSQL: `core.symbol_vector_links` ---[/bold cyan]"
    )
    try:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT vector_id FROM core.symbol_vector_links ORDER BY vector_id")
            )
            db_point_ids = [str(row.vector_id) for row in result]

        if not db_point_ids:
            console.print("[yellow]No vector links found in the database.[/yellow]")
            return

        console.print(f"Found {len(db_point_ids)} vector IDs in PostgreSQL:")
        for i, vector_id in enumerate(db_point_ids):
            console.print(f"{i+1:4d}: {vector_id}")

    except Exception as e:
        console.print(f"[bold red]An error occurred during PostgreSQL query: {e}[/bold red]")


async def list_qdrant_point_ids():
    """Connects ONLY to Qdrant and prints all point IDs from the collection."""
    console.print(
        f"\n[bold cyan]--- Querying Qdrant Collection: `{settings.QDRANT_COLLECTION_NAME}` ---[/bold cyan]"
    )
    try:
        qdrant_client = AsyncQdrantClient(url=settings.QDRANT_URL)
        qdrant_point_ids = set()
        offset = None
        while True:
            records, next_page_offset = await qdrant_client.scroll(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                limit=1000,
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

        if not qdrant_point_ids:
            console.print("[yellow]No points found in the Qdrant collection.[/yellow]")
            return
            
        sorted_ids = sorted(list(qdrant_point_ids))
        console.print(f"Found {len(sorted_ids)} point IDs in Qdrant:")
        for i, point_id in enumerate(sorted_ids):
            console.print(f"{i+1:4d}: {point_id}")

    except Exception as e:
        console.print(f"[bold red]An error occurred during Qdrant query: {e}[/bold red]")


async def main():
    await list_postgres_vector_ids()
    await list_qdrant_point_ids()


if __name__ == "__main__":
    asyncio.run(main())