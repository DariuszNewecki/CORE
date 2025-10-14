# src/cli/logic/diagnostics/vector_drift.py
from __future__ import annotations

import asyncio

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlalchemy import text

from services.clients.qdrant_client import QdrantService
from services.database.session_manager import get_session

console = Console()


async def _fetch_postgres_vector_ids() -> set[str]:
    """
    Authoritative source of vector IDs is the link table:
      core.symbol_vector_links(symbol_id UUID, vector_id TEXT, ...)
    """
    async with get_session() as session:
        rows = await session.execute(
            text("SELECT vector_id::text FROM core.symbol_vector_links")
        )
        return {r[0] for r in rows}


async def _fetch_qdrant_point_ids() -> set[str]:
    """
    Fetch all point IDs from Qdrant without payloads/vectors.
    """
    service = QdrantService()
    all_ids: set[str] = set()
    offset = None

    # Scroll through the whole collection to be robust with >10k points
    while True:
        points, offset = await service.client.scroll(
            collection_name=service.collection_name,
            limit=10_000,
            with_payload=False,
            with_vectors=False,
            offset=offset,
        )
        all_ids.update(str(p.id) for p in points)
        if offset is None:
            break

    return all_ids


# ID: 87360a13-844e-4528-a444-5677e7c83841
async def inspect_vector_drift() -> None:
    console.print(
        "[bold cyan]🚀 Verifying synchronization between PostgreSQL and Qdrant...[/bold cyan]"
    )

    try:
        postgres_ids, qdrant_ids = await asyncio.gather(
            _fetch_postgres_vector_ids(), _fetch_qdrant_point_ids()
        )
    except Exception as e:
        console.print(f"[bold red]❌ Error connecting to a database: {e}[/bold red]")
        return

    console.print(f"   -> Found {len(postgres_ids)} linked vector IDs in PostgreSQL.")
    console.print(f"   -> Found {len(qdrant_ids)} point IDs in Qdrant.")

    missing_in_qdrant = sorted(postgres_ids - qdrant_ids)
    orphans_in_qdrant = sorted(qdrant_ids - postgres_ids)

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
            caption="Exists in Postgres link table but missing from Qdrant.",
            header_style="bold yellow",
        )
        table.add_column("Vector ID (expected in Qdrant)")
        for vid in missing_in_qdrant[:200]:
            table.add_row(vid)
        if len(missing_in_qdrant) > 200:
            table.add_row(f"... and {len(missing_in_qdrant) - 200} more")
        console.print(table)
        console.print(
            "\n[bold]Next step:[/bold] Recreate with `poetry run core-admin knowledge vectorize --write`."
        )

    if orphans_in_qdrant:
        table = Table(
            title=f"🧹 Orphaned in Qdrant ({len(orphans_in_qdrant)})",
            caption="Present in Qdrant but no link in Postgres.",
            header_style="bold magenta",
        )
        table.add_column("Orphaned Point ID (Qdrant only)")
        for pid in orphans_in_qdrant[:200]:
            table.add_row(pid)
        if len(orphans_in_qdrant) > 200:
            table.add_row(f"... and {len(orphans_in_qdrant) - 200} more")
        console.print(table)
        console.print(
            "\n[bold]Next step:[/bold] `poetry run core-admin fix orphaned-vectors --dry-run`, then without `--dry-run`."
        )
