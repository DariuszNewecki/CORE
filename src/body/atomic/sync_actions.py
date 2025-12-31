# src/body/atomic/sync_actions.py
# ID: atomic.sync
"""
Atomic Sync Actions - State Synchronization

Each action synchronizes one aspect of system state:
- Database knowledge graph
- Vector embeddings
- Constitutional documents

Actions are independent, composable, and auditable.
"""

from __future__ import annotations

import time

from body.atomic.registry import ActionCategory, register_action
from features.introspection.sync_service import run_sync_with_db
from features.introspection.vectorization_service import run_vectorize
from shared.action_types import ActionResult
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.vector.adapters.constitutional_adapter import (
    ConstitutionalAdapter,
)
from shared.logger import getLogger


logger = getLogger(__name__)


@register_action(
    action_id="sync.db",
    description="Sync code symbols to PostgreSQL knowledge graph",
    category=ActionCategory.SYNC,
    policies=["database_schema"],
    impact_level="moderate",
    requires_db=True,
)
# ID: f6789012-3456-789a-bcde-f0123456789a
async def action_sync_database(
    core_context: CoreContext, write: bool = False
) -> ActionResult:
    """
    Synchronize code symbols to PostgreSQL knowledge graph.

    Args:
        core_context: CORE context with services
        write: Apply changes (default: dry-run)

    Returns:
        ActionResult with symbols_synced count
    """
    start = time.time()
    try:
        logger.info("Syncing symbols to database")

        if not write:
            # Dry-run mode - just report
            return ActionResult(
                action_id="sync.db",
                ok=True,
                data={
                    "symbols_synced": 0,
                    "relationships_created": 0,
                    "dry_run": True,
                },
                duration_sec=time.time() - start,
            )

        async with get_session() as session:
            # run_sync_with_db only takes session parameter
            stats = await run_sync_with_db(session)

        return ActionResult(
            action_id="sync.db",
            ok=True,
            data={
                "symbols_synced": stats.get("scanned", 0),
                "inserted": stats.get("inserted", 0),
                "updated": stats.get("updated", 0),
                "deleted": stats.get("deleted", 0),
                "dry_run": False,
            },
            duration_sec=time.time() - start,
        )
    except Exception as e:
        logger.error("Database sync failed: %s", e, exc_info=True)
        return ActionResult(
            action_id="sync.db",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start,
        )


@register_action(
    action_id="sync.vectors.code",
    description="Vectorize code symbols to Qdrant",
    category=ActionCategory.SYNC,
    policies=["vector_storage_policy"],
    impact_level="moderate",
    requires_db=True,
    requires_vectors=True,
)
# ID: 0123456789ab-cdef-0123-4567-89abcdef0123
# ID: af6a56d0-b2d3-44fe-b6ea-55d6aed3768b
async def action_sync_code_vectors(
    core_context: CoreContext, write: bool = False, force: bool = False
) -> ActionResult:
    """
    Vectorize code symbols and sync to Qdrant.

    Args:
        core_context: CORE context with services
        write: Apply changes (default: dry-run)
        force: Force re-vectorization of all symbols

    Returns:
        ActionResult with vectors_synced count
    """
    start = time.time()
    try:
        logger.info("Vectorizing code symbols")

        async with get_session() as session:
            await run_vectorize(
                context=core_context,
                session=session,
                dry_run=not write,
                force=force,
            )

        return ActionResult(
            action_id="sync.vectors.code",
            ok=True,
            data={
                "status": "completed",
                "dry_run": not write,
                "force": force,
            },
            duration_sec=time.time() - start,
        )
    except Exception as e:
        logger.error("Code vectorization failed: %s", e, exc_info=True)
        return ActionResult(
            action_id="sync.vectors.code",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start,
        )


@register_action(
    action_id="sync.vectors.constitution",
    description="Vectorize constitutional documents (policies, patterns)",
    category=ActionCategory.SYNC,
    policies=["vector_storage_policy"],
    impact_level="safe",
    requires_vectors=True,
)
# ID: 23456789abcd-ef01-2345-6789-abcdef012345
# ID: b301871b-6205-4300-a76e-65d2ffa56c03
async def action_sync_constitutional_vectors(
    core_context: CoreContext, write: bool = False
) -> ActionResult:
    """
    Vectorize constitutional documents to Qdrant with smart deduplication.

    This syncs:
    - Policy documents from .intent/policies/
    - Pattern documents from .intent/charter/patterns/

    Uses VectorIndexService with CognitiveService embedder for:
    - Hash-based deduplication (only vectorize changed content)
    - Database-configured LLM providers (same as code vectorization)
    - Batch processing with proper error handling

    Args:
        core_context: CORE context with services
        write: Apply changes (default: dry-run)

    Returns:
        ActionResult with policies_indexed and patterns_indexed counts
    """
    start = time.time()

    try:
        logger.info("Vectorizing constitutional documents")

        if not write:
            logger.info("Dry-run: would vectorize constitutional documents")
            return ActionResult(
                action_id="sync.vectors.constitution",
                ok=True,
                data={"dry_run": True, "status": "skipped"},
                duration_sec=time.time() - start,
            )

        # Get cognitive service (same path as code vectorization)
        cognitive_service = core_context.cognitive_service
        if cognitive_service is None and hasattr(core_context, "registry"):
            cognitive_service = await core_context.registry.get_cognitive_service()

        if cognitive_service is None:
            logger.info(
                "Cognitive service not available, skipping constitutional vectorization"
            )
            return ActionResult(
                action_id="sync.vectors.constitution",
                ok=True,
                data={"status": "skipped", "reason": "cognitive_service_unavailable"},
                duration_sec=time.time() - start,
            )

        # Pre-flight check (same as code vectorization)
        logger.info("Testing embedding service...")
        try:
            test_embedding = await cognitive_service.get_embedding_for_code("test")
            if not test_embedding:
                raise RuntimeError("Embedding service returned empty result")
        except Exception as e:
            logger.info(
                "Embedding service unavailable, skipping constitutional vectorization: %s",
                e,
            )
            return ActionResult(
                action_id="sync.vectors.constitution",
                ok=True,
                data={"status": "skipped", "reason": "embedding_service_unavailable"},
                duration_sec=time.time() - start,
            )

        # Create embedder adapter to wrap CognitiveService
        from shared.infrastructure.vector.cognitive_adapter import (
            CognitiveEmbedderAdapter,
        )
        from shared.infrastructure.vector.vector_index_service import VectorIndexService

        embedder = CognitiveEmbedderAdapter(cognitive_service)
        adapter = ConstitutionalAdapter()

        # Vectorize policies with smart deduplication
        policy_items = adapter.policies_to_items()
        logger.info("Found %d policy chunks to process", len(policy_items))

        policy_service = VectorIndexService(
            qdrant_service=core_context.qdrant_service,
            collection_name="core_policies",
            embedder=embedder,  # Inject CognitiveService!
        )
        await policy_service.ensure_collection()
        policy_results = await policy_service.index_items(policy_items, batch_size=10)

        # Vectorize patterns with smart deduplication
        pattern_items = adapter.patterns_to_items()
        logger.info("Found %d pattern chunks to process", len(pattern_items))

        pattern_service = VectorIndexService(
            qdrant_service=core_context.qdrant_service,
            collection_name="core-patterns",
            embedder=embedder,  # Inject CognitiveService!
        )
        await pattern_service.ensure_collection()
        pattern_results = await pattern_service.index_items(
            pattern_items, batch_size=10
        )

        return ActionResult(
            action_id="sync.vectors.constitution",
            ok=True,
            data={
                "policies_count": len(policy_items),
                "policies_indexed": len(policy_results),
                "patterns_count": len(pattern_items),
                "patterns_indexed": len(pattern_results),
            },
            duration_sec=time.time() - start,
        )
    except Exception as e:
        logger.error("Constitutional vectorization failed: %s", e, exc_info=True)
        return ActionResult(
            action_id="sync.vectors.constitution",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start,
        )
