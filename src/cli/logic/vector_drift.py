# src/cli/logic/diagnostics/vector_drift.py
from __future__ import annotations

import asyncio

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from services.clients.qdrant_client import QdrantService
from services.database.session_manager import get_session
from sqlalchemy import text

console = Console()


async def _fetch_postgres_vector_ids() -> set[str]:
    """Fetches all symbol IDs that should have a vector from the main DB."""
    async with get_session() as session:
        # We cast the UUID to text to ensure it matches Qdrant's string-based IDs.
        result = await session.execute(
            text("SELECT id::text FROM core.symbols WHERE vector_id IS NOT NULL")
        )
        return {row[0] for row in result}


async def _fetch_qdrant_point_ids() -> set[str]:
    """Fetches all point IDs from the Qdrant vector collection."""
    qdrant_service = QdrantService()
    # Scroll through all points without fetching payloads or vectors for efficiency.
    all_points, _ = await qdrant_service.client.scroll(
        collection_name=qdrant_service.collection_name,
        limit=10000,  # Adjust if you have more than 10k vectors
        with_payload=False,
        with_vectors=False,
    )
    return {str(point.id) for point in all_points}


# ID: 687c5d83-2353-4522-aecd-c07162a42d80
async def inspect_vector_drift():
    """Compares Postgres and Qdrant to find synchronization drift."""
    console.print(
        "[bold cyan]🚀 Verifying synchronization between PostgreSQL and Qdrant...[/bold cyan]"
    )

    try:
        db_ids, qdrant_ids = await asyncio.gather(
            _fetch_postgres_vector_ids(), _fetch_qdrant_point_ids()
        )
    except Exception as e:
        console.print(f"[bold red]❌ Error connecting to a database: {e}[/bold red]")
        return

    console.print(f"   -> Found {len(db_ids)} vectorized symbols in PostgreSQL.")
    console.print(f"   -> Found {len(qdrant_ids)} points in Qdrant.")

    missing_in_qdrant = sorted(list(db_ids - qdrant_ids))
    orphans_in_qdrant = sorted(list(qdrant_ids - db_ids))

    console.print("\n--- Verification Result ---")
    if not missing_in_qdrant and not orphans_in_qdrant:
        console.print(
            Panel(
                "[bold green]✅ Perfect Synchronization.[/bold green]\nPostgreSQL and Qdrant are perfectly aligned.",
                title="Status",
                border_style="green",
            )
        )
        return

    if missing_in_qdrant:
        table = Table(
            title=f"⚠️ Missing in Qdrant ({len(missing_in_qdrant)})",
            caption="These symbols exist in Postgres but are missing from the vector index.",
            header_style="bold yellow",
        )
        table.add_column("PostgreSQL Symbol ID")
        for symbol_id in missing_in_qdrant:
            table.add_row(symbol_id)
        console.print(table)
        console.print(
            "\n[bold]Next Step:[/bold] Run `core-admin run vectorize --write` to fix."
        )

    if orphans_in_qdrant:
        table = Table(
            title=f"👻 Orphans in Qdrant ({len(orphans_in_qdrant)})",
            caption="These vectors exist in Qdrant but their symbols are gone from Postgres.",
            header_style="bold red",
        )
        table.add_column("Orphaned Qdrant Point ID")
        for point_id in orphans_in_qdrant:
            table.add_row(point_id)
        console.print(table)
        console.print(
            "\n[bold]Next Step:[/bold] Run `core-admin fix orphaned-vectors --write` to fix."
        )
