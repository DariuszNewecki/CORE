# src/body/services/governance_claims_service.py
"""
Governance Claims Service - Body Layer

Manages the Qdrant `governance_claims` collection that backs the CCC
SAMECONCERN and R1_SCOPED checks per ADR-073 D4 / D5.

Responsibilities:
  - Collection presence check (vector-dependent checks refuse when empty)
  - Idempotent upsert of harvested Claim objects (incremental contract)
  - Delete-by-source-path for artifacts removed from the corpus
  - Search wrapper returning (cosine, payload) tuples for the tiered policy

No settings access; constructor takes a QdrantService via DI.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from qdrant_client.http import models as qm

from shared.logger import getLogger


if TYPE_CHECKING:
    from body.governance.coherence_harvester import Claim
    from shared.infrastructure.clients.qdrant_client import QdrantService


logger = getLogger(__name__)


GOVERNANCE_CLAIMS_COLLECTION = "governance_claims"


@dataclass(frozen=True)
# ID: 24f7da2c-c76d-4a6a-9620-d92a9b32f835
class ClaimVector:
    """A claim paired with its embedding vector, ready for upsert."""

    claim: Claim
    vector: list[float]


@dataclass(frozen=True)
# ID: 5bc46b63-224d-49d7-81ca-72d0995772bb
class SearchHit:
    """One hit from a kNN search against governance_claims."""

    cosine: float
    source_path: str
    paragraph_index: int
    text: str
    content_sha: str
    category: str


# ID: f1fdd5bd-bfc6-45cc-86a2-745629f17202
class GovernanceClaimsService:
    """Qdrant-backed store for governance normative claims."""

    # ID: ee68153e-7367-45e8-853e-bd7250c77708
    def __init__(self, qdrant: QdrantService, vector_size: int = 768) -> None:
        self._qdrant = qdrant
        self._vector_size = vector_size

    @property
    # ID: d579e0ca-aa2c-41f4-98a2-9ebd0acdb640
    def collection_name(self) -> str:
        return GOVERNANCE_CLAIMS_COLLECTION

    # ID: 6ca4d304-c3de-43b6-9888-cfcc072a7f28
    async def is_seeded(self) -> bool:
        """Return True iff the collection exists AND has ≥1 point.

        Vector-dependent CCC checks (SAMECONCERN, R1_SCOPED) refuse to emit
        when this returns False, per ADR-073 D4.
        """
        try:
            collections = await self._qdrant.client.get_collections()
        except Exception as exc:
            logger.warning(
                "governance_claims: failed to list Qdrant collections: %s", exc
            )
            return False
        names = {c.name for c in collections.collections}
        if self.collection_name not in names:
            return False
        try:
            info = await self._qdrant.client.get_collection(self.collection_name)
        except Exception as exc:
            logger.warning("governance_claims: failed to inspect collection: %s", exc)
            return False
        return (info.points_count or 0) > 0

    # ID: 496e1f73-60d5-4812-9347-91a078340d8a
    async def ensure_collection(self) -> None:
        """Create the collection if absent. Idempotent."""
        await self._qdrant.ensure_collection(
            collection_name=self.collection_name,
            vector_size=self._vector_size,
        )

    # ID: 681683dd-1bb7-4118-8f31-580cc5433e38
    async def upsert_claims(self, items: Sequence[ClaimVector]) -> int:
        """Upsert (point_id, vector, payload) tuples; returns count written.

        Point identity is (source_path, content_sha) — paragraph reordering
        does not force re-embedding.
        """
        if not items:
            return 0
        points = [
            qm.PointStruct(
                id=_point_id(cv.claim.source_path, cv.claim.content_sha),
                vector=cv.vector,
                payload={
                    "source_path": cv.claim.source_path,
                    "paragraph_index": cv.claim.paragraph_index,
                    "line": cv.claim.line,
                    "text": cv.claim.text,
                    "category": cv.claim.category,
                    "content_sha": cv.claim.content_sha,
                },
            )
            for cv in items
        ]
        await self._qdrant.upsert_points(self.collection_name, points, wait=True)
        return len(points)

    # ID: 0b95b690-181b-48de-89bd-719648812305
    async def delete_by_source_path(self, source_path: str) -> None:
        """Remove all points belonging to a single source artifact."""
        await self._qdrant.client.delete(
            collection_name=self.collection_name,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(
                    must=[
                        qm.FieldCondition(
                            key="source_path",
                            match=qm.MatchValue(value=source_path),
                        )
                    ]
                )
            ),
            wait=True,
        )

    # ID: 1fd1324e-7b1c-4bf3-914c-c5faf22a2354
    async def current_keys(self) -> set[tuple[str, str]]:
        """Return {(source_path, content_sha)} for every point in the collection.

        The set is the canonical "what's already embedded" view used by the
        sync worker to compute the incremental diff in O(corpus + collection).
        Identity is content-keyed, so paragraph reordering within a file does
        not force re-embedding.
        """
        records = await self._qdrant.scroll_all_points(
            with_payload=True,
            with_vectors=False,
            page_size=1024,
            collection_name=self.collection_name,
        )
        result: set[tuple[str, str]] = set()
        for record in records:
            payload = record.payload or {}
            source_path = payload.get("source_path")
            content_sha = payload.get("content_sha")
            if isinstance(source_path, str) and isinstance(content_sha, str):
                result.add((source_path, content_sha))
        return result

    # ID: 04a0c52c-6a14-469a-a85b-19b0c978c3d5
    async def delete_by_keys(self, keys: Sequence[tuple[str, str]]) -> int:
        """Delete points by (source_path, content_sha). Returns count."""
        if not keys:
            return 0
        point_ids = [_point_id(path, sha) for path, sha in keys]
        await self._qdrant.client.delete(
            collection_name=self.collection_name,
            points_selector=qm.PointIdsList(points=point_ids),
            wait=True,
        )
        return len(point_ids)

    # ID: 644e1d97-0c04-4788-8523-79707f59db45
    async def search(
        self,
        query_vector: list[float],
        limit: int = 10,
        score_threshold: float | None = None,
        source_path_in: list[str] | None = None,
    ) -> list[SearchHit]:
        """kNN search returning enriched hits for the tiered-cosine policy (D5).

        `source_path_in`, when set, restricts hits to claims from the listed
        artifacts — used by R1_SCOPED (D2) to bound search to declared
        `Relates:` pairs.
        """
        query_filter = None
        if source_path_in:
            query_filter = qm.Filter(
                must=[
                    qm.FieldCondition(
                        key="source_path",
                        match=qm.MatchAny(any=source_path_in),
                    )
                ]
            )
        scored = await self._qdrant.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=query_filter,
        )
        hits: list[SearchHit] = []
        for s in scored:
            payload = s.payload or {}
            hits.append(
                SearchHit(
                    cosine=float(s.score),
                    source_path=str(payload.get("source_path", "")),
                    paragraph_index=int(payload.get("paragraph_index", 0)),
                    text=str(payload.get("text", "")),
                    content_sha=str(payload.get("content_sha", "")),
                    category=str(payload.get("category", "")),
                )
            )
        return hits


def _point_id(source_path: str, content_sha: str) -> str:
    """Deterministic UUID5 from (source_path, content_sha)."""
    import uuid

    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_path}::{content_sha}"))
