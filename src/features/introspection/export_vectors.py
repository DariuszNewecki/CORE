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
from qdrant_client.http import models as qm

from shared.context import CoreContext
from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.logger import getLogger


logger = getLogger(__name__)


async def _async_export(qdrant_service: QdrantService, output_path: Path):
    """The core async logic for exporting vectors."""
    logger.info("Exporting all vectors to %s...", output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        all_vectors: list[qm.Record] = await qdrant_service.get_all_vectors()
        if not all_vectors:
            logger.info("No vectors found in the database to export.")
            return
        count = 0
        with output_path.open("w", encoding="utf-8") as f:
            for record in all_vectors:
                vector_data = record.vector
                if hasattr(vector_data, "tolist"):
                    vector_data = vector_data.tolist()
                line_data = {
                    "id": str(record.id),
                    "payload": record.payload,
                    "vector": vector_data,
                }
                f.write(json.dumps(line_data) + "\n")
                count += 1
        logger.info("Successfully exported %s vectors.", count)
    except Exception as e:
        logger.error("Failed to export vectors: %s", e, exc_info=True)
        raise typer.Exit(code=1)


# ID: c94d2b2e-fde1-4ee8-bfe7-608e5d9bd18a
def export_vectors(
    ctx: typer.Context,
    output: Path = typer.Option(
        "reports/vectors_export.jsonl",
        "--output",
        "-o",
        help="The path to save the exported JSONL file.",
    ),
):
    """Exports all vectors from Qdrant to a JSONL file."""
    core_context: CoreContext = ctx.obj
    asyncio.run(_async_export(core_context.qdrant_service, output))
