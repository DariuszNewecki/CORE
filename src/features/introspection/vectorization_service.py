# src/features/introspection/vectorization_service.py
"""
High-performance orchestrator for capability vectorization.
MODULARIZED V2.4: Reduced Modularity Debt by delegating to specialized neurons.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.context import CoreContext
from shared.infrastructure.config_service import ConfigService
from shared.logger import getLogger

from .vectorization.db_queries import fetch_initial_state, finalize_vector_update
from .vectorization.delta_analyzer import DeltaAnalyzer
from .vectorization.embedding_logic import get_robust_embedding


logger = getLogger(__name__)


# ID: 0e545e4a-22e4-42cc-b1f6-9e900445627b
async def run_vectorize(
    context: CoreContext,
    session: AsyncSession,
    dry_run: bool = False,
    force: bool = False,
) -> None:
    """Orchestrates the full vectorization workflow via Component Delegation."""
    config = await ConfigService.create(session)
    if not await config.get_bool("LLM_ENABLED", default=False):
        logger.info("Vectorization skipped: LLM_ENABLED=false")
        return

    strict = await config.get_bool("VECTORIZATION_STRICT", default=True)
    logger.info("🚀 Starting Modular Vectorization...")

    # 1. SETUP: Gather infrastructure
    qdrant = context.qdrant_service or await context.registry.get_qdrant_service()
    cog = await context.registry.get_cognitive_service()
    await qdrant.ensure_collection()

    # 2. ANALYSIS: Identify Deltas (Delegated to DeltaAnalyzer)
    all_symbols, existing_links = await fetch_initial_state(session)
    stored_hashes = await qdrant.get_stored_hashes()

    analyzer = DeltaAnalyzer(settings.REPO_PATH, stored_hashes)
    tasks = analyzer.identify_changes(all_symbols, existing_links, force)

    if not tasks:
        logger.info("✅ Vector knowledge base is already up-to-date.")
        return

    if dry_run:
        logger.info("[DRY RUN] %d symbols need update.", len(tasks))
        return

    # 3. EXECUTION: Embedding Loop
    updates, failures = [], []
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
            failures.append((t["path"], str(e)))
            logger.error("Failed symbol %s: %s", t["path"], e)

    # 4. FINALIZE: Persist to DB
    if updates:
        await finalize_vector_update(session, updates)
        await session.commit()

    _report_final_status(len(updates), len(tasks), failures, strict)


def _report_final_status(success_count: int, total: int, failures: list, strict: bool):
    logger.info(
        "🏁 Finished. Processed %d/%d (failures=%d).",
        success_count,
        total,
        len(failures),
    )
    if failures and strict:
        raise RuntimeError(f"Vectorization degraded: {len(failures)} failures.")
