# src/body/atomic/sync_actions/sync_actions.py
# sync_actions.py
"""The three action functions (database sync, code vector sync, constitutional vector sync) remain together as a cohesive group of synchronization actions."""

from __future__ import annotations

import time

from body.atomic.registry import ActionCategory, register_action
from body.introspection.sync_service import run_sync_with_db
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.vector.adapters.constitutional_adapter import (
    ConstitutionalAdapter,
)
from shared.logger import getLogger


logger = getLogger(__name__)

from .chunking_helpers import _chunk_file, _embed_and_upsert


@register_action(
    action_id="sync.db",
    description="Synchronize code symbols to PostgreSQL knowledge graph",
    category=ActionCategory.SYNC,
    policies=["rules/architecture/blackboard"],
)
@atomic_action(
    action_id="sync.db",
    intent="Atomic action for sync.db",
    impact=ActionImpact.WRITE_METADATA,
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
    description="Vectorize codebase artifacts to Qdrant",
    category=ActionCategory.SYNC,
    policies=["rules/architecture/blackboard"],
)
@atomic_action(
    action_id="sync.vectors.code",
    intent="Atomic action for sync.vectors.code",
    impact=ActionImpact.WRITE_METADATA,
    policies=["atomic_actions"],
)
# ID: af6a56d0-b2d3-44fe-b6ea-55d6aed3768b
async def action_sync_code_vectors(
    core_context: CoreContext, write: bool = False, force: bool = False
) -> ActionResult:
    """
    Vectorize codebase artifacts to Qdrant by calling Body services directly.

    Pipeline:
      1. CrawlService.run_crawl() — walks repo, registers artifacts in
         core.repo_artifacts, extracts AST call-graph edges.
      2. ArtifactService — fetches unembedded artifacts in batches; chunking
         and Qdrant upsert handled by module-level helpers defined in this file.
    """
    from shared.infrastructure.bootstrap_registry import BootstrapRegistry
    from shared.infrastructure.clients.qdrant_client import QdrantService

    start = time.time()

    try:
        if not write:
            logger.info(
                "Dry-run: would run CrawlService.run_crawl + ArtifactService embed loop"
            )
            return ActionResult(
                action_id="sync.vectors.code",
                ok=True,
                data={"status": "dry_run"},
                duration_sec=time.time() - start,
            )

        repo_root = BootstrapRegistry.get_repo_path()
        crawl_svc = await core_context.registry.get_crawl_service()
        artifact_svc = await core_context.registry.get_artifact_service()

        cognitive_service = core_context.cognitive_service
        if cognitive_service is None and hasattr(core_context, "registry"):
            cognitive_service = await core_context.registry.get_cognitive_service()

        # Phase 1: Crawl — register/update repo_artifacts and call-graph edges
        logger.info("sync.vectors.code: Phase 1 — CrawlService.run_crawl")
        await crawl_svc.run_crawl(repo_root, cognitive_service)

        # Phase 2: Embed — chunk and upsert all pending artifacts in batches
        logger.info("sync.vectors.code: Phase 2 — ArtifactService embed loop")
        qdrant = QdrantService()

        max_passes = 500
        for pass_num in range(1, max_passes + 1):
            pending = await artifact_svc.count_pending_artifacts()
            if pending == 0:
                logger.info(
                    "sync.vectors.code: all artifacts embedded after %d pass(es)",
                    pass_num - 1,
                )
                break
            logger.info(
                "sync.vectors.code: embedding pass %d (%d artifacts pending)",
                pass_num,
                pending,
            )
            artifacts = await artifact_svc.fetch_unembedded_artifacts(batch_size=10)
            if not artifacts:
                break

            for artifact in artifacts:
                artifact_id = artifact["id"]
                file_path_str = artifact["file_path"]
                artifact_type = artifact["artifact_type"]
                collection = artifact["qdrant_collection"]

                full_path = repo_root / file_path_str
                if not full_path.exists():
                    logger.warning("sync.vectors.code: file missing: %s", file_path_str)
                    continue

                try:
                    chunks = _chunk_file(full_path, artifact_type)
                    if not chunks:
                        await artifact_svc.mark_artifact_empty(artifact_id)
                        logger.info(
                            "sync.vectors.code: empty file skipped permanently: %s",
                            file_path_str,
                        )
                        continue

                    chunk_count = await _embed_and_upsert(
                        chunks=chunks,
                        collection=collection,
                        file_path=file_path_str,
                        artifact_type=artifact_type,
                        qdrant=qdrant,
                        cognitive=cognitive_service,
                    )

                    await artifact_svc.update_artifact_chunk_count(
                        artifact_id, chunk_count
                    )
                    logger.info(
                        "sync.vectors.code: embedded %s → %d chunks → %s",
                        file_path_str,
                        chunk_count,
                        collection,
                    )
                except Exception as exc:
                    logger.warning(
                        "sync.vectors.code: failed to embed %s: %s",
                        file_path_str,
                        exc,
                    )
        else:
            logger.warning(
                "sync.vectors.code: reached max embedding passes (%d)", max_passes
            )

        return ActionResult(
            action_id="sync.vectors.code",
            ok=True,
            data={"status": "completed", "dry_run": False},
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
    description="Vectorize constitutional documents to Qdrant",
    category=ActionCategory.SYNC,
    policies=["rules/architecture/blackboard"],
)
@atomic_action(
    action_id="sync.vectors.constitution",
    intent="Atomic action for sync.vectors.constitution",
    impact=ActionImpact.WRITE_METADATA,
    policies=["atomic_actions"],
)
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

        # Specs Sync
        from shared.infrastructure.vector.adapters.specs_adapter import SpecsAdapter

        specs_adapter = SpecsAdapter()
        specs_items = specs_adapter.docs_to_items()
        specs_service = VectorIndexService(
            qdrant_service=core_context.qdrant_service,
            collection_name="core_specs",
            embedder=embedder,
        )
        await specs_service.ensure_collection()
        specs_results = await specs_service.index_items(specs_items, batch_size=10)

        return ActionResult(
            action_id="sync.vectors.constitution",
            ok=True,
            data={
                "policies_count": len(policy_items),
                "policies_indexed": len(policy_results),
                "patterns_count": len(pattern_items),
                "patterns_indexed": len(pattern_results),
                "specs_count": len(specs_items),
                "specs_indexed": len(specs_results),
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
