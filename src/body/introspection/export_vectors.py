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

from qdrant_client.http import models as qm

# REFACTORED: Removed direct settings import
from shared.exceptions import CoreError
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext
    from shared.infrastructure.clients.qdrant_client import QdrantService
    from shared.infrastructure.storage.file_handler import FileHandler

logger = getLogger(__name__)


# ID: 3196d095-9e61-4dbe-952c-dc4b7ea7c8e2
class VectorExportError(CoreError):
    """Raised when vector export cannot complete."""


def _normalize_output_path(output_path: Path, repo_root: Path) -> str:
    """
    Convert the provided path to a repository-relative POSIX string.

    Raises VectorExportError if the path escapes the repository boundary.
    """
    try:
        if output_path.is_absolute():
            rel_path = output_path.relative_to(repo_root)
        else:
            rel_path = output_path
        return str(rel_path).replace("\\", "/")
    except ValueError as exc:
        logger.error("Output path %s must be within the repository root.", output_path)
        raise VectorExportError(
            "Output path must be within the repository root.", exit_code=1
        ) from exc


async def _async_export(
    qdrant_service: QdrantService,
    file_handler: FileHandler,
    output_path: Path,
    repo_root: Path,
):
    """
    The core async logic for exporting vectors.
    Mutations are routed through the governed FileHandler.
    """

    # 1. Path Normalization
    # Convert absolute or relative path to a repo-relative string for the FileHandler
    rel_path_str = _normalize_output_path(output_path, repo_root)

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
        raise VectorExportError("Failed to export vectors.", exit_code=1) from e


# ID: 9d8d50b8-b533-4169-b21f-839a06db1f46
async def export_vectors(
    context: CoreContext, output: Path | str = Path("reports/vectors_export.jsonl")
) -> None:
    """Exports all vectors from Qdrant to a JSONL file via governed services."""
    output_path = Path(output)
    if not getattr(context, "qdrant_service", None) or not getattr(
        context, "file_handler", None
    ):
        raise VectorExportError(
            "CoreContext must provide qdrant_service and file_handler.", exit_code=1
        )

    await _async_export(
        context.qdrant_service,
        context.file_handler,
        output_path,
        context.git_service.repo_path,
    )
