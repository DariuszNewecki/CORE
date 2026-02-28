# src/will/tools/policy_vectorizer.py

"""
Policy Vectorization Tool - A2 Enhanced

Orchestrates the semantic indexing of constitutional policies.
Uses the unified VectorIndexService for smart deduplication.

CONSTITUTIONAL ALIGNMENT:
- Aligned with 'async.no_manual_loop_run' via Defensive Loop Guard.
- Aligned with 'logic.logging.standard_only' (removed print statements).
- Follows 'dry_by_design' by using shared infrastructure adapters.
- Honestly Async: No thread-spawning or loop hijacking.
- Complies with RUF006 using a module-level task registry to prevent GC.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.infrastructure.vector.adapters.constitutional_adapter import (
    ConstitutionalAdapter,
)
from shared.infrastructure.vector.vector_index_service import VectorIndexService
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)

# Canonical collection for policies
POLICY_COLLECTION = "core_policies"

# RUF006 FIX: Persistent set to hold references to running tasks
_RUNNING_TASKS: set[asyncio.Task] = set()


# ID: 106d06ad-6291-4deb-8af1-8edafba3f45d
class PolicyVectorizer:
    """
    Tool for vectorizing constitutional policies for semantic search.

    This is a Body-layer tool that delegates the heavy lifting to the
    ConstitutionalAdapter (Mind-to-Vector mapping) and
    VectorIndexService (Persistence).
    """

    def __init__(
        self,
        repo_root: Path,
        cognitive_service: CognitiveService,
        qdrant_service: QdrantService,
    ):
        self.repo_root = Path(repo_root)
        self.cognitive = cognitive_service
        self.qdrant = qdrant_service

        # We wrap the CognitiveService so the Indexer can use the DB-configured LLM
        from shared.infrastructure.vector.cognitive_adapter import (
            CognitiveEmbedderAdapter,
        )

        self.embedder = CognitiveEmbedderAdapter(cognitive_service)

    # ID: c10418a1-7dbe-4b26-90cd-e87e1711bc1b
    async def vectorize_all_policies(self) -> dict[str, Any]:
        """
        Orchestrates the full vectorization process.

        Uses smart deduplication: only changed policies are re-embedded.
        """
        logger.info("=" * 60)
        logger.info("🚀 STARTING CONSTITUTIONAL VECTOR SYNC")
        logger.info("=" * 60)

        # 1. Initialize Infrastructure
        adapter = ConstitutionalAdapter()
        service = VectorIndexService(
            qdrant_service=self.qdrant,
            collection_name=POLICY_COLLECTION,
            embedder=self.embedder,
        )

        await service.ensure_collection()

        # 2. Extract Items (delegated to Mind-layer adapter)
        items = adapter.policies_to_items()
        logger.info("Found %d semantic chunks in .intent/", len(items))

        # 3. Execute Indexing (delegated to Body-layer service)
        results = await service.index_items(items, batch_size=10)

        logger.info("=" * 60)
        logger.info("✅ SYNC COMPLETE")
        logger.info("   Chunks Processed: %d", len(items))
        logger.info("   Updated/Indexed:  %d", len(results))
        logger.info("=" * 60)

        return {
            "success": True,
            "policies_vectorized": len(set(i.payload["doc_id"] for i in items)),
            "chunks_created": len(items),
            "indexed_count": len(results),
        }

    # ID: 5f79e8a2-8cde-4245-ad6f-b4bd355b238c
    async def search_policies(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search for relevant policy chunks."""
        service = VectorIndexService(
            qdrant_service=self.qdrant,
            collection_name=POLICY_COLLECTION,
            embedder=self.embedder,
        )
        return await service.query(query, limit=limit)


# ID: 64c63d13-45c0-4ef5-9001-42703a6158a6
async def vectorize_policies_command(repo_root: Path) -> dict[str, Any]:
    """CLI command wrapper for policy vectorization."""
    qdrant_service = QdrantService()
    cognitive_service = CognitiveService(
        repo_path=repo_root, qdrant_service=qdrant_service
    )
    await cognitive_service.initialize()

    vectorizer = PolicyVectorizer(repo_root, cognitive_service, qdrant_service)
    return await vectorizer.vectorize_all_policies()


# ID: 5ccf49ce-779c-443a-b03b-188d77602a90
def run_as_script():
    """
    Constitutional entry point for standalone execution.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Vectorize constitutional policies into Qdrant."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Path to the CORE repository root.",
    )

    args = parser.parse_args()

    async def _main() -> None:
        """Internal main logic."""
        try:
            result = await vectorize_policies_command(args.repo_root)
            logger.info(
                "Success! Vectorized %s policies.", result.get("policies_vectorized", 0)
            )
        except Exception as e:
            logger.error("Vectorization failed: %s", e)

    # THE DEFENSIVE GUARD:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # RUF006 COMPLIANCE: Use a strong reference in a module-level set.
        task = asyncio.create_task(_main())
        _RUNNING_TASKS.add(task)
        task.add_done_callback(_RUNNING_TASKS.discard)
    else:
        asyncio.run(_main())


if __name__ == "__main__":
    run_as_script()
