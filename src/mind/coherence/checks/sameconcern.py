# src/mind/coherence/checks/sameconcern.py
"""SAMECONCERN — §6.1 same-concern contradiction via vector kNN + LLM judge.

Per ADR-073 D5 tiered cosine policy. Refuses if governance_claims is not
seeded (per D4 governor-CLI bootstrap posture).

Mechanism:
  1. Batch-embed all sampled claims in one round-trip (#478).
  2. For each (claim, vector), kNN-search governance_claims.
  3. Tier each hit: high-confidence (≥0.78), ambiguous (0.74-0.78), drop (<0.74).
  4. Forward both tiers to the LLM judge (ambiguous tier gets a different prompt).
  5. Dedupe pairs across the bi-directional iteration.

Cosine thresholds are tunable per D5 telemetry feedback; defaults live here.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.logger import getLogger

from ..llm_judge import judge_contradiction_pair
from .base import CoherenceCandidate


if TYPE_CHECKING:
    from body.services.governance_claims_service import GovernanceClaimsService
    from shared.governance.coherence_harvester import NormativeMarkerRegister


logger = getLogger(__name__)


_HIGH_CONFIDENCE_COSINE = 0.78
_AMBIGUOUS_COSINE = 0.74
_KNN_LIMIT = 10
_DEFAULT_MAX_QUERIES = 200


# ID: 5be96f7c-4c2b-4946-819a-b118b0535e19
class SameConcernCheck:
    """Emit SAMECONCERN candidates for contradicting pairs flagged by kNN + LLM."""

    relation = "SAMECONCERN"

    # ID: b34dfca3-3cb3-49e6-97c1-cd65bfdeb228
    def __init__(
        self,
        repo_root: Path,
        register: NormativeMarkerRegister,
        claims_service: GovernanceClaimsService,
        cognitive_service: Any,
        max_queries: int | None = _DEFAULT_MAX_QUERIES,
    ) -> None:
        self._repo_root = Path(repo_root)
        self._register = register
        self._claims_service = claims_service
        self._cognitive_service = cognitive_service
        self._max_queries = max_queries

    # ID: 43f12752-e72e-43e4-9d87-027d762e4e9e
    async def run(self) -> list[CoherenceCandidate]:
        from shared.governance.coherence_harvester import GovernanceClaimHarvester
        from shared.infrastructure.vector.cognitive_adapter import (
            CognitiveEmbedderAdapter,
        )

        if not await self._claims_service.is_seeded():
            logger.info(
                "SAMECONCERN: governance_claims collection not seeded; "
                "skipping (run `core-admin coherence seed bootstrap` per D4)"
            )
            return []

        harvester = GovernanceClaimHarvester(self._repo_root, self._register)
        claims = list(harvester.harvest())
        if self._max_queries is not None and len(claims) > self._max_queries:
            import random

            random.seed(42)
            claims = random.sample(claims, self._max_queries)

        embedder = CognitiveEmbedderAdapter(self._cognitive_service)
        seen: set[frozenset[tuple[str, str]]] = set()
        candidates: list[CoherenceCandidate] = []

        # Batch-embed all query claims in a single round-trip (#478).
        try:
            vectors = await embedder.get_embeddings_batch([c.text for c in claims])
        except Exception as exc:
            logger.warning(
                "SAMECONCERN: batch embed failed for %d claims: %s — skipping run",
                len(claims),
                exc,
            )
            return []

        for claim, vector in zip(claims, vectors):
            hits = await self._claims_service.search(
                query_vector=vector,
                limit=_KNN_LIMIT,
                score_threshold=_AMBIGUOUS_COSINE,
            )

            for hit in hits:
                if (
                    hit.source_path == claim.source_path
                    and hit.content_sha == claim.content_sha
                ):
                    continue
                tier = (
                    "high_confidence"
                    if hit.cosine >= _HIGH_CONFIDENCE_COSINE
                    else "ambiguous"
                )
                pair_key: frozenset[tuple[str, str]] = frozenset(
                    {
                        (claim.source_path, claim.content_sha),
                        (hit.source_path, hit.content_sha),
                    }
                )
                if pair_key in seen:
                    continue
                seen.add(pair_key)

                verdict = await judge_contradiction_pair(
                    cognitive_service=self._cognitive_service,
                    text_a=claim.text,
                    source_a=claim.source_path,
                    text_b=hit.text,
                    source_b=hit.source_path,
                    tier=tier,
                    relation=self.relation,
                    category_a=claim.category,
                    category_b=hit.category,
                )
                if verdict is not None:
                    candidates.append(verdict)

        return candidates
