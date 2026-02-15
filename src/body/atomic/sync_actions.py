# src/body/atomic/sync_actions.py
# ID: e664ac9c-d51f-4dd8-864d-ed67d3c3c479
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
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
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
    policies=["rules/data/governance"],
    impact_level="moderate",
    requires_db=True,
)
@atomic_action(
    action_id="sync.db",
    intent="Atomic action for action_sync_database",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: f6789012-3456-789a-bcde-f0123456789a
async def action_sync_database(
    core_context: CoreContext, write: bool = False
) -> ActionResult:
    """
    Synchronize code symbols to PostgreSQL knowledge graph.
    """
    start = time.time()
    try:
        logger.info("Syncing symbols to database")

        if not write:
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
            # FIXED: Wrapped in begin() to ensure the sync is committed to the Mind
            async with session.begin():
                result_obj = await run_sync_with_db(session)

        stats = result_obj.data

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
    policies=["rules/data/governance"],
    impact_level="moderate",
    requires_db=True,
    requires_vectors=True,
)
@atomic_action(
    action_id="sync.vectors.code",
    intent="Atomic action for action_sync_code_vectors",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 9825c54f-d3a5-49cb-af17-8dde9f8366a8
# ID: af6a56d0-b2d3-44fe-b6ea-55d6aed3768b
async def action_sync_code_vectors(
    core_context: CoreContext, write: bool = False, force: bool = False
) -> ActionResult:
    """
    Vectorize code symbols and sync to Qdrant.
    """
    start = time.time()
    try:
        logger.info("Vectorizing code symbols")

        async with get_session() as session:
            # CRITICAL CONSTITUTIONAL FIX: Added session.begin()
            # run_vectorize prepares the data, but session.begin() ensures the
            # "Last Embedded" timestamps are actually SAVED in PostgreSQL.
            async with session.begin():
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
    policies=["rules/data/governance"],
    impact_level="safe",
    requires_vectors=True,
)
@atomic_action(
    action_id="sync.vectors.constitution",
    intent="Atomic action for action_sync_constitutional_vectors",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 6995c29a-581a-499d-9b3d-6b9664b5963d
# ID: b301871b-6205-4300-a76e-65d2ffa56c03
async def action_sync_constitutional_vectors(
    core_context: CoreContext, write: bool = False
) -> ActionResult:
    """
    Vectorize constitutional documents to Qdrant with smart deduplication.
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

        cognitive_service = core_context.cognitive_service
        if cognitive_service is None and hasattr(core_context, "registry"):
            cognitive_service = await core_context.registry.get_cognitive_service()

        if cognitive_service is None:
            return ActionResult(
                action_id="sync.vectors.constitution",
                ok=True,
                data={"status": "skipped", "reason": "cognitive_service_unavailable"},
                duration_sec=time.time() - start,
            )

        # Pre-flight check
        try:
            await cognitive_service.get_embedding_for_code("test")
        except Exception as e:
            return ActionResult(
                action_id="sync.vectors.constitution",
                ok=True,
                data={
                    "status": "skipped",
                    "reason": f"embedding_service_unavailable: {e}",
                },
                duration_sec=time.time() - start,
            )

        from shared.infrastructure.vector.cognitive_adapter import (
            CognitiveEmbedderAdapter,
        )
        from shared.infrastructure.vector.vector_index_service import VectorIndexService

        embedder = CognitiveEmbedderAdapter(cognitive_service)
        adapter = ConstitutionalAdapter()

        # Policy Sync
        policy_items = adapter.policies_to_items()
        policy_service = VectorIndexService(
            qdrant_service=core_context.qdrant_service,
            collection_name="core_policies",
            embedder=embedder,
        )
        await policy_service.ensure_collection()
        policy_results = await policy_service.index_items(policy_items, batch_size=10)

        # Pattern Sync
        pattern_items = adapter.patterns_to_items()
        pattern_service = VectorIndexService(
            qdrant_service=core_context.qdrant_service,
            collection_name="core-patterns",
            embedder=embedder,
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
