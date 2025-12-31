# src/features/introspection/export_vectors.py
# ID: c94d2b2e-fde1-4ee8-bfe7-608e5d9bd18a

"""
A utility to export all vectors and their payloads from the Qdrant database
to a local JSONL file for analysis, clustering, or backup.

Refactored to use the canonical FileHandler for governed report persistence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from qdrant_client.http import models as qm

from shared.cli_utils import core_command
from shared.config import settings
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


async def _async_export(context: CoreContext, output_path: Path):
    """
    The core async logic for exporting vectors.
    Mutations are routed through the governed FileHandler.
    """
    repo_root = settings.REPO_PATH
    qdrant_service = context.qdrant_service
    file_handler = context.file_handler

    # 1. Path Normalization
    # Convert absolute or relative path to a repo-relative string for the FileHandler
    try:
        if output_path.is_absolute():
            rel_path = output_path.relative_to(repo_root)
        else:
            # If it's already relative, ensure it's relative to root, not CWD
            rel_path = output_path

        rel_path_str = str(rel_path).replace("\\", "/")
    except ValueError:
        logger.error("Output path %s must be within the repository root.", output_path)
        raise typer.Exit(code=1)

    logger.info("Exporting all vectors to %s...", rel_path_str)

    try:
        # 2. Data Retrieval
        all_vectors: list[qm.Record] = await qdrant_service.get_all_vectors()
        if not all_vectors:
            logger.info("No vectors found in the database to export.")
            return

        # 3. Content Preparation (JSONL format)
        lines = []
        for record in all_vectors:
            vector_data = record.vector
            if hasattr(vector_data, "tolist"):
                vector_data = vector_data.tolist()

            line_data = {
                "id": str(record.id),
                "payload": record.payload,
                "vector": vector_data,
            }
            lines.append(json.dumps(line_data, ensure_ascii=False))

        content = "\n".join(lines) + "\n"

        # 4. Governed Write
        # ensure_dir and write_runtime_text enforce IntentGuard and log the action
        file_handler.ensure_dir(str(Path(rel_path_str).parent))
        file_handler.write_runtime_text(rel_path_str, content)

        logger.info(
            "Successfully exported %s vectors via FileHandler.", len(all_vectors)
        )

    except Exception as e:
        logger.error("Failed to export vectors: %s", e, exc_info=True)
        raise typer.Exit(code=1)


# ID: c94d2b2e-fde1-4ee8-bfe7-608e5d9bd18a
@core_command(dangerous=False)
# ID: a609ada6-bc85-463c-9db4-93c59924c4ef
async def export_vectors(
    ctx: typer.Context,
    output: Path = typer.Option(
        "reports/vectors_export.jsonl",
        "--output",
        "-o",
        help="The path to save the exported JSONL file.",
    ),
):
    """Exports all vectors from Qdrant to a JSONL file via governed services."""
    core_context: CoreContext = ctx.obj
    await _async_export(core_context, output)
