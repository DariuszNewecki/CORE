# src/cli/resources/vectors/rebuild.py
"""`core-admin vectors rebuild` — rebuild a Qdrant collection from scratch.

Replaces the structurally-broken command removed in #201 (it called
delete_collection then logged fake "Recreated"/"Re-indexed" success with no
underlying work). A real rebuild is three coordinated operations (#203):

  1. Delete the Qdrant collection.
  2. Reset ``core.repo_artifacts.chunk_count = 0`` for the rows targeting that
     collection (skipping permanently-empty ``-1`` rows) so RepoEmbedderWorker
     re-selects them (its claim query is ``WHERE chunk_count = 0``).
  3. RepoEmbedderWorker repopulates organically on its next cycle — it
     ``ensure_collection``s on first upsert, so the collection is recreated
     with current vectors (e.g. after an embedding-model change).

Destructive: dry-run by default; ``--write`` applies.
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console
from sqlalchemy import text

from cli.utils import core_command
from shared.infrastructure.database.session_manager import get_session

from .hub import app


logger = logging.getLogger(__name__)
console = Console()


def _ensure_known_collection(collection: str, known: list[str]) -> None:
    """Refuse to rebuild a collection Qdrant does not currently hold.

    A typo'd or unknown name must never reach delete_collection — that is the
    primary safety guard for this destructive command.
    """
    if collection not in known:
        console.print(
            f"[red]Unknown collection '{collection}'.[/red] Known: "
            f"{', '.join(sorted(known)) or '(none)'}"
        )
        raise typer.Exit(1)


@app.command("rebuild")
@core_command(dangerous=True, requires_context=True)
# ID: f0398939-3c90-4972-b8bf-1241dcc6b732
async def rebuild_collection(
    ctx: typer.Context,
    collection: str = typer.Option(
        ...,
        "--collection",
        "-c",
        help="Qdrant collection to rebuild (e.g. core-code, core-specs).",
    ),
    write: bool = typer.Option(
        False, "--write", help="Apply the rebuild (default: dry-run)."
    ),
) -> None:
    """Delete a Qdrant collection and reset chunk_count so it repopulates.

    Dry-run by default — shows how many artifacts would be re-embedded.
    Pass --write to delete the collection and reset chunk_count; the
    RepoEmbedderWorker then repopulates on its next cycle.
    """
    qdrant = ctx.obj.qdrant_service
    known = await qdrant.list_collections()
    _ensure_known_collection(collection, known)

    async with get_session() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT count(*) AS total,
                           count(*) FILTER (WHERE chunk_count > 0) AS embedded
                    FROM core.repo_artifacts
                    WHERE qdrant_collection = :c
                    """
                ),
                {"c": collection},
            )
        ).one()
    total, embedded = row.total, row.embedded

    console.print(f"[bold cyan]Vector rebuild — {collection}[/bold cyan]")
    console.print(f"Artifacts targeting collection: {total} (embedded: {embedded})")
    console.print(f"Mode: {'WRITE' if write else 'DRY-RUN'}")

    if not write:
        console.print(
            f"[yellow]DRY-RUN:[/yellow] would delete Qdrant collection "
            f"'{collection}' and reset chunk_count=0 on {embedded} embedded "
            f"artifact(s) for re-embedding. Use --write to apply."
        )
        return

    # 1. Delete the Qdrant collection.
    await qdrant.client.delete_collection(collection_name=collection)
    console.print(f"[green]Deleted[/green] Qdrant collection '{collection}'.")

    # 2. Reset chunk_count so RepoEmbedderWorker re-selects the rows. Leave
    #    permanently-empty (-1) rows untouched — re-embedding empties is a no-op.
    async with get_session() as session:
        result = await session.execute(
            text(
                """
                UPDATE core.repo_artifacts
                SET chunk_count = 0
                WHERE qdrant_collection = :c AND chunk_count > 0
                """
            ),
            {"c": collection},
        )
        await session.commit()
    console.print(
        f"[green]Reset[/green] chunk_count=0 on {result.rowcount} artifact(s)."
    )
    console.print(
        "[dim]RepoEmbedderWorker will recreate the collection and repopulate "
        "on its next cycle (it ensure_collections on first upsert).[/dim]"
    )
