# src/shared/tools/policy_vectorizer.py
"""Policy Vectorization Tool — semantic indexing of constitutional policies."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.infrastructure.intent.operational_config import load_operational_config
from shared.infrastructure.vector.adapters.constitutional_adapter import (
    ConstitutionalAdapter,
)
from shared.infrastructure.vector.cognitive_adapter import CognitiveEmbedderAdapter
from shared.infrastructure.vector.vector_index_service import VectorIndexService
from shared.logger import getLogger


if TYPE_CHECKING:
    from will.orchestration.cognitive_service import CognitiveService

_CFG_VEC = load_operational_config().vectors

logger = getLogger(__name__)

POLICY_COLLECTION = "core_policies"


# ID: 106d06ad-6291-4deb-8af1-8edafba3f45d
class PolicyVectorizer:
    """Tool for vectorizing constitutional policies for semantic search."""

    def __init__(
        self,
        repo_root: Path,
        cognitive_service: CognitiveService,
        qdrant_service: QdrantService,
    ):
        self.repo_root = Path(repo_root)
        self.cognitive = cognitive_service
        self.qdrant = qdrant_service
        self.embedder = CognitiveEmbedderAdapter(cognitive_service)

    # ID: c10418a1-7dbe-4b26-90cd-e87e1711bc1b
    async def vectorize_all_policies(self) -> dict[str, Any]:
        """Orchestrate the full vectorization process with smart deduplication."""
        logger.info("=" * 60)
        logger.info("🚀 STARTING CONSTITUTIONAL VECTOR SYNC")
        logger.info("=" * 60)

        adapter = ConstitutionalAdapter()
        service = VectorIndexService(
            qdrant_service=self.qdrant,
            collection_name=POLICY_COLLECTION,
            embedder=self.embedder,
        )
        await service.ensure_collection()

        items = adapter.policies_to_items()
        logger.info("Found %d semantic chunks in .intent/", len(items))

        results = await service.index_items(
            items, batch_size=_CFG_VEC.policy_vectorizer_batch_size
        )

        logger.info("=" * 60)
        logger.info("✅ SYNC COMPLETE")
        logger.info("   Chunks Processed: %d", len(items))
        logger.info("   Updated/Indexed:  %d", len(results))
        logger.info("=" * 60)

        return {
            "success": True,
            "policies_vectorized": len({i.payload["doc_id"] for i in items}),
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
