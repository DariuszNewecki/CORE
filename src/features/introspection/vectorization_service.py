# src/features/introspection/vectorization_service.py

"""
High-performance orchestrator for capability vectorization.
"""

from __future__ import annotations

import ast
import asyncio
import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from shared.config import settings
from shared.context import CoreContext
from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger
from shared.utils.embedding_utils import normalize_text


if TYPE_CHECKING:
    from will.orchestration.cognitive_service import CognitiveService
logger = getLogger(__name__)


async def _fetch_all_public_symbols_from_db() -> list[dict]:
    """Queries the database for all public symbols."""
    from sqlalchemy import text

    async with get_session() as session:
        stmt = text(
            "\n            SELECT id, symbol_path, module, fingerprint AS structural_hash\n            FROM core.symbols\n            WHERE is_public = TRUE\n            "
        )
        result = await session.execute(stmt)
        return [dict(row._mapping) for row in result]


async def _fetch_existing_vector_links() -> dict[str, str]:
    """Fetches all existing symbol_id -> vector_id mappings from the database."""
    from sqlalchemy import text

    async with get_session() as session:
        result = await session.execute(
            text("SELECT symbol_id, vector_id FROM core.symbol_vector_links")
        )
        return {str(row.symbol_id): str(row.vector_id) for row in result}


async def _get_stored_vector_hashes(qdrant_service: QdrantService) -> dict[str, str]:
    """
    Fetches all point IDs and their content hashes from Qdrant.

    PHASE 1 FIX: Uses scroll_all_points() service method instead of manual pagination.
    """
    hashes = {}
    try:
        points = await qdrant_service.scroll_all_points(
            with_payload=True, with_vectors=False
        )
        for point in points:
            if point.payload and "content_sha256" in point.payload:
                hashes[str(point.id)] = point.payload.get("content_sha256")
        logger.debug("Retrieved %s content hashes from Qdrant", len(hashes))
    except Exception as e:
        logger.warning(
            "Could not retrieve hashes from Qdrant (will re-vectorize all): %s", e
        )
    return hashes


def _get_source_code(file_path: Path, symbol_path: str) -> str | None:
    """Extracts the source code of a specific symbol from a file using AST."""
    if not file_path.exists():
        logger.warning(
            "Source file not found for symbol %s at path %s", symbol_path, file_path
        )
        return None
    content = file_path.read_text("utf-8", errors="ignore")
    try:
        tree = ast.parse(content)
        target_name = symbol_path.split("::")[-1]
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if hasattr(node, "name") and node.name == target_name:
                    return ast.get_source_segment(content, node)
    except Exception:
        return None
    return None


async def _get_robust_embedding(
    cognitive_service: CognitiveService, text: str
) -> list[float] | None:
    """
    Gets embedding with fallback strategy.
    """
    try:
        return await cognitive_service.get_embedding_for_code(text)
    except RuntimeError as e:
        if "Ghost Vector" in str(e) or "Embedding model failed" in str(e):
            mid = len(text) // 2
            logger.warning(
                "Ghost Vector detected. Retrying with split strategy (len=%d).",
                len(text),
            )
            part1 = text[:mid]
            part2 = text[mid:]
            v1 = await cognitive_service.get_embedding_for_code(part1)
            v2 = await cognitive_service.get_embedding_for_code(part2)
            if v1 and v2:
                import numpy as np

                avg = (np.array(v1) + np.array(v2)) / 2.0
                norm = np.linalg.norm(avg)
                if norm > 0:
                    avg = avg / norm
                return avg.tolist()
        raise e


async def _process_vectorization_task(
    task: dict,
    cognitive_service: CognitiveService,
    qdrant_service: QdrantService,
    failure_log_path: Path,
) -> str | None:
    """Processes a single symbol: gets embedding and upserts to Qdrant."""
    try:
        source_code = task["source_code"]
        vector = await _get_robust_embedding(cognitive_service, source_code)
        if not vector:
            raise ValueError("Embedding service returned None")
        point_id = str(task["id"])
        payload_data = {
            "source_path": task["file_path_str"],
            "source_type": "code",
            "chunk_id": task["symbol_path"],
            "content_sha256": task["code_hash"],
            "language": "python",
            "symbol": task["symbol_path"],
            "capability_tags": [point_id],
        }
        await qdrant_service.upsert_capability_vector(
            point_id_str=point_id, vector=vector, payload_data=payload_data
        )
        return point_id
    except Exception as e:
        logger.error("Failed to process symbol '%s': %s", task["symbol_path"], e)
        failure_log_path.parent.mkdir(parents=True, exist_ok=True)
        with failure_log_path.open("a", encoding="utf-8") as f:
            f.write(f"vectorization_error\t{task['symbol_path']}\t{e}\n")
        return None


async def _update_db_after_vectorization(updates: list[dict]):
    """Creates links in symbol_vector_links and updates the last_embedded timestamp."""
    from sqlalchemy import text

    if not updates:
        return
    async with get_session() as session:
        async with session.begin():
            await session.execute(
                text(
                    "\n                    INSERT INTO core.symbol_vector_links (symbol_id, vector_id, embedding_model, embedding_version, created_at)\n                    VALUES (:symbol_id, :vector_id, :embedding_model, :embedding_version, NOW())\n                    ON CONFLICT (symbol_id) DO UPDATE SET\n                        vector_id = EXCLUDED.vector_id,\n                        embedding_model = EXCLUDED.embedding_model,\n                        embedding_version = EXCLUDED.embedding_version,\n                        created_at = NOW();\n                "
                ),
                updates,
            )
            await session.execute(
                text(
                    "UPDATE core.symbols SET last_embedded = NOW() WHERE id = ANY(:symbol_ids)"
                ),
                {"symbol_ids": [u["symbol_id"] for u in updates]},
            )
    logger.info("Updated %d records in the database.", len(updates))


# ID: 0e545e4a-22e4-42cc-b1f6-9e900445627b
async def run_vectorize(
    context: CoreContext, dry_run: bool = False, force: bool = False
):
    """
    The main orchestration logic for vectorizing capabilities based on the database.
    """
    logger.info("Starting Database-Driven Vectorization...")
    failure_log_path = settings.REPO_PATH / "logs" / "vectorization_failures.log"
    from shared.infrastructure.config_service import ConfigService

    async with get_session() as session:
        config = await ConfigService.create(session)
        llm_enabled = await config.get_bool("LLM_ENABLED", default=False)
    if not llm_enabled:
        logger.warning("LLM_ENABLED is False. Skipping vectorization.")
        return
    cognitive_service = context.cognitive_service
    logger.info("Performing pre-flight check on embedding service...")
    try:
        check = await cognitive_service.get_embedding_for_code("test")
        if not check:
            raise RuntimeError("Embedding service returned empty result")
        logger.info("Embedding service is healthy.")
    except Exception as e:
        logger.error("❌ Embedding service unreachable: %s", e)
        logger.error(
            "Skipping vectorization phase. Ensure your LLM provider is running."
        )
        return
    all_symbols, existing_links, stored_vector_hashes = await asyncio.gather(
        _fetch_all_public_symbols_from_db(),
        _fetch_existing_vector_links(),
        _get_stored_vector_hashes(context.qdrant_service),
    )
    qdrant_service = context.qdrant_service
    await qdrant_service.ensure_collection()
    tasks = []
    for symbol in all_symbols:
        symbol_id_str = str(symbol["id"])
        module_path = symbol["module"]
        file_path_str = "src/" + module_path.replace(".", "/") + ".py"
        file_path = settings.REPO_PATH / file_path_str
        source_code = _get_source_code(file_path, symbol["symbol_path"])
        if not source_code:
            continue
        normalized_code = normalize_text(source_code)
        current_code_hash = hashlib.sha256(normalized_code.encode("utf-8")).hexdigest()
        needs_vectorization = False
        if force:
            needs_vectorization = True
        elif symbol_id_str not in existing_links:
            needs_vectorization = True
        else:
            vector_id = existing_links[symbol_id_str]
            stored_hash = stored_vector_hashes.get(vector_id)
            if current_code_hash != stored_hash:
                needs_vectorization = True
        if needs_vectorization:
            task_data = {
                **symbol,
                "source_code": normalized_code,
                "code_hash": current_code_hash,
                "file_path_str": str(file_path.relative_to(settings.REPO_PATH)),
            }
            tasks.append(task_data)
    if not tasks:
        logger.info("Vector knowledge base is already up-to-date.")
        return
    logger.info("Found %d symbols needing vectorization.", len(tasks))
    if dry_run:
        logger.info("DRY RUN: No embeddings will be generated.")
        return
    updates_to_db = []
    success_count = 0
    total = len(tasks)
    for i, task in enumerate(tasks, 1):
        if i % 10 == 0:
            logger.info("Vectorizing... (%d/%d)", i, total)
        point_id = await _process_vectorization_task(
            task, cognitive_service, qdrant_service, failure_log_path
        )
        if point_id:
            success_count += 1
            updates_to_db.append(
                {
                    "symbol_id": task["id"],
                    "vector_id": point_id,
                    "embedding_model": settings.LOCAL_EMBEDDING_MODEL_NAME,
                    "embedding_version": 1,
                }
            )
        else:
            pass
    await _update_db_after_vectorization(updates_to_db)
    logger.info(
        "Vectorization complete. Processed %d/%d symbols.", success_count, total
    )
    if len(updates_to_db) < total:
        logger.warning(
            "%d failures logged to %s", total - len(updates_to_db), failure_log_path
        )
