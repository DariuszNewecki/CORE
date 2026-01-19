# src/features/introspection/vectorization_service.py
"""
High-performance orchestrator for capability vectorization.
Preserves all robustness logic via high-fidelity modularization.
"""

from __future__ import annotations

import hashlib

from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.context import CoreContext
from shared.infrastructure.config_service import ConfigService
from shared.logger import getLogger
from shared.utils.embedding_utils import normalize_text

from .vectorization.code_processor import extract_symbol_source
from .vectorization.db_queries import fetch_initial_state, finalize_vector_update
from .vectorization.embedding_logic import get_robust_embedding


logger = getLogger(__name__)


# ID: 0e545e4a-22e4-42cc-b1f6-9e900445627b
async def run_vectorize(
    context: CoreContext,
    session: AsyncSession,
    dry_run: bool = False,
    force: bool = False,
):
    """Orchestrates the full vectorization workflow."""
    config = await ConfigService.create(session)
    if not await config.get_bool("LLM_ENABLED", default=False):
        return

    logger.info("🚀 Starting High-Fidelity Vectorization...")
    qdrant = context.qdrant_service or await context.registry.get_qdrant_service()
    cog = await context.registry.get_cognitive_service()

    # 1. PARALLEL SENSE: DB State + Qdrant Hashes
    await qdrant.ensure_collection()
    all_symbols, existing_links = await fetch_initial_state(session)
    stored_hashes = await qdrant.get_stored_hashes()

    # 2. ANALYZE DELTA: Deduplication logic
    tasks = []
    for sym in all_symbols:
        rel_path = f"src/{sym['module'].replace('.', '/')}.py"
        source = extract_symbol_source(
            settings.REPO_PATH / rel_path, sym["symbol_path"]
        )
        if not source:
            continue

        norm_code = normalize_text(source)
        code_hash = hashlib.sha256(norm_code.encode("utf-8")).hexdigest()

        needs_vec = (
            force
            or str(sym["id"]) not in existing_links
            or code_hash != stored_hashes.get(existing_links.get(str(sym["id"])))
        )

        if needs_vec:
            tasks.append(
                {
                    "id": sym["id"],
                    "path": sym["symbol_path"],
                    "source": norm_code,
                    "hash": code_hash,
                    "file": rel_path,
                }
            )

    if not tasks:
        logger.info("✅ Vector knowledge base is already up-to-date.")
        return

    if dry_run:
        logger.info("[DRY RUN] %d symbols need update.", len(tasks))
        return

    # 3. EXECUTE: Loop with progress and robust error handling
    updates = []
    for i, t in enumerate(tasks, 1):
        if i % 10 == 0:
            logger.info("Progress: %d/%d", i, len(tasks))
        try:
            vec = await get_robust_embedding(cog, t["source"])
            p_id = str(t["id"])
            payload = {
                "source_path": t["file"],
                "source_type": "code",
                "chunk_id": t["path"],
                "content_sha256": t["hash"],
                "language": "python",
                "symbol": t["path"],
            }
            await qdrant.upsert_capability_vector(p_id, vec, payload)
            updates.append(
                {
                    "symbol_id": t["id"],
                    "vector_id": p_id,
                    "embedding_model": settings.LOCAL_EMBEDDING_MODEL_NAME,
                    "embedding_version": 1,
                }
            )
        except Exception as e:
            logger.error("Failed symbol %s: %s", t["path"], e)

    # 4. FINALIZE: Transactional update
    await finalize_vector_update(session, updates)
    await session.commit()
    logger.info("🏁 Vectorization complete. Processed %d symbols.", len(updates))
