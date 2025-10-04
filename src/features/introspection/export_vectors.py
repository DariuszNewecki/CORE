# src/features/introspection/export_vectors.py
"""
A utility to export all vectors and their payloads from the Qdrant database
to a local JSONL file for analysis, clustering, or backup.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import track
from services.clients.qdrant_client import QdrantService
from shared.logger import getLogger

log = getLogger("export_vectors")
console = Console()


async def _async_export(output_path: Path):
    """The core async logic for exporting vectors."""
    console.print(
        f"🚀 Exporting all vectors to [bold cyan]{output_path}[/bold cyan]..."
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    qdrant_service = QdrantService()

    try:
        all_vectors = await qdrant_service.get_all_vectors()

        if not all_vectors:
            console.print(
                "[yellow]No vectors found in the database to export.[/yellow]"
            )
            return

        count = 0
        with output_path.open("w", encoding="utf-8") as f:
            for record in track(all_vectors, description="Writing vectors..."):
                line_data = {
                    "id": record.id,
                    "payload": record.payload,
                    "vector": record.vector,
                }
                f.write(json.dumps(line_data) + "\n")
                count += 1

        console.print(
            f"[bold green]✅ Successfully exported {count} vectors.[/bold green]"
        )

    except Exception as e:
        log.error(f"Failed to export vectors: {e}", exc_info=True)
        console.print(f"[bold red]❌ An error occurred during export: {e}[/bold red]")
        raise typer.Exit(code=1)


# ID: 51a560a2-7304-49d9-9b31-364cc68ae0c3
def export_vectors(
    output: Path = typer.Option(
        "reports/vectors_export.jsonl",
        "--output",
        "-o",
        help="The path to save the exported JSONL file.",
    ),
):
    """Exports all vectors from Qdrant to a JSONL file."""
    asyncio.run(_async_export(output))


if __name__ == "__main__":
    typer.run(export_vectors)
