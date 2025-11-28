# src/body/cli/logic/vector_drift.py
"""Provides functionality for the vector_drift module."""

from __future__ import annotations

import asyncio

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from services.clients.qdrant_client import QdrantService
from services.database.session_manager import get_session
from shared.context import CoreContext
from sqlalchemy import text

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


async def _fetch_qdrant_point_ids(qdrant_service: QdrantService) -> set[str]:
    """
    Fetch all point IDs from Qdrant without payloads/vectors.
    """
    # Use the passed-in service instance instead of creating a new one
    all_ids: set[str] = set()
    offset = None

    # Scroll through the whole collection to be robust with >10k points
    while True:
        points, offset = await qdrant_service.client.scroll(
            collection_name=qdrant_service.collection_name,
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
async def inspect_vector_drift(context: CoreContext) -> None:
    """
    Verifies synchronization between PostgreSQL and Qdrant using the
    context's QdrantService.
    """
    console.print(
        "[bold cyan]🚀 Verifying synchronization between PostgreSQL and Qdrant...[/bold cyan]"
    )

    # === JIT INJECTION ===
    if context.qdrant_service is None and context.registry:
        try:
            context.qdrant_service = await context.registry.get_qdrant_service()
        except Exception as e:
            console.print(
                f"[bold red]❌ Failed to initialize QdrantService: {e}[/bold red]"
            )
            return

    if not context.qdrant_service:
        console.print("[bold red]❌ QdrantService not available in context.[/bold red]")
        return

    try:
        postgres_ids, qdrant_ids = await asyncio.gather(
            _fetch_postgres_vector_ids(),
            _fetch_qdrant_point_ids(context.qdrant_service),
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
