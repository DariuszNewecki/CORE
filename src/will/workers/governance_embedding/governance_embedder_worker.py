# src/will/workers/governance_embedding/governance_embedder_worker.py
"""Worker that maintains the Qdrant governance_claims collection per ADR-073 D4.

Steady-state incremental sync only — first-time seeding is the governor's
`core-admin coherence seed bootstrap` operation. If the collection is absent
or empty when this worker runs, it logs and returns; it does NOT auto-seed.

Constitutional grounding:
  - ADR-073 D4 (sync worker mandate)
  - ADR-018 D3a/b (decomposed crawler/embedder precedent)
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shared.logger import getLogger
from shared.workers.scheduled_worker import ScheduledWorker


logger = getLogger(__name__)


# ID: 130f77a0-7c07-4dae-994e-c769e7f48fbe
class GovernanceEmbedderWorker(ScheduledWorker):
    """Sensing worker that incrementally embeds governance normative claims.

    Per ADR-073 D4:
      - The incremental contract is constitutional: a claim is re-embedded
        only when its content_sha differs from the stored value.
      - Bootstrap is NOT performed here. If the collection is absent or
        empty, the worker logs and returns without writing.
      - Full-corpus re-embed per cycle is forbidden.
    """

    declaration_name = "governance_embedder"

    # ID: bedcfbf0-63f4-4af2-a86d-e023f16e9fbe
    def __init__(self, cognitive_service: Any = None) -> None:
        from shared.infrastructure.bootstrap_registry import BootstrapRegistry

        super().__init__()
        self._cognitive_service = cognitive_service
        self._repo_root: Path = BootstrapRegistry.get_repo_path()
        schedule = self._declaration.get("mandate", {}).get("schedule", {})
        self._batch_size: int = schedule.get("batch_size", 50)

    async def _before_loop(self) -> None:
        """Lazy-load CognitiveService if not injected (daemon context)."""
        from body.services.service_registry import service_registry

        if self._cognitive_service is None:
            self._cognitive_service = await service_registry.get_cognitive_service()

    # ID: 4c7e0f2a-786d-4423-97d5-060b7e67eee7
    async def run(self) -> None:
        """Embed governance claims whose content_sha differs from the store.

        Refuses (logs + returns) when the collection has not been seeded by
        the governor's bootstrap CLI per D4.
        """
        await self.post_heartbeat()

        from body.services.governance_claims_service import (
            ClaimVector,
            GovernanceClaimsService,
        )
        from body.services.service_registry import service_registry
        from shared.governance.coherence_harvester import GovernanceClaimHarvester
        from shared.infrastructure.vector.cognitive_adapter import (
            CognitiveEmbedderAdapter,
        )

        qdrant = await service_registry.get_qdrant_service()
        claims_service = GovernanceClaimsService(qdrant)

        if not await claims_service.is_seeded():
            logger.info(
                "GovernanceEmbedderWorker: collection not seeded; "
                "awaiting `core-admin coherence seed bootstrap` (D4)"
            )
            return

        if self._cognitive_service is None:
            self._cognitive_service = await service_registry.get_cognitive_service()
        embedder = CognitiveEmbedderAdapter(self._cognitive_service)

        harvester = GovernanceClaimHarvester(self._repo_root)
        harvested = list(harvester.harvest())
        harvested_keys = {(c.source_path, c.content_sha): c for c in harvested}

        existing_keys = await claims_service.current_keys()

        new_keys = set(harvested_keys.keys()) - existing_keys
        stale_keys = existing_keys - set(harvested_keys.keys())

        to_embed = [harvested_keys[k] for k in new_keys][: self._batch_size]
        items: list[ClaimVector] = []
        failures = 0
        if to_embed:
            try:
                vectors = await embedder.get_embeddings_batch(
                    [c.text for c in to_embed]
                )
                items = [
                    ClaimVector(claim=c, vector=v) for c, v in zip(to_embed, vectors)
                ]
            except Exception as exc:
                logger.warning(
                    "GovernanceEmbedderWorker: batch embed failed for %d claims "
                    "(%s); falling back to single-shot for this cycle",
                    len(to_embed),
                    exc,
                )
                for claim in to_embed:
                    try:
                        vector = await embedder.get_embedding(claim.text)
                    except Exception as exc2:
                        logger.warning(
                            "GovernanceEmbedderWorker: single-shot embed failed "
                            "for %s (sha=%s): %s",
                            claim.source_path,
                            claim.content_sha[:8],
                            exc2,
                        )
                        failures += 1
                        continue
                    items.append(ClaimVector(claim=claim, vector=vector))

        added = await claims_service.upsert_claims(items)
        deleted = await claims_service.delete_by_keys(list(stale_keys))

        await self.post_report(
            subject="governance.embed.complete",
            payload={
                "harvested_total": len(harvested),
                "embedded_added": added,
                "deleted_stale": deleted,
                "embed_failures": failures,
                "pending_after_batch": max(0, len(new_keys) - len(to_embed)),
                "completed_at": datetime.now(UTC).isoformat(),
            },
        )
        logger.info(
            "GovernanceEmbedderWorker: cycle complete — added=%d deleted=%d failures=%d pending=%d",
            added,
            deleted,
            failures,
            max(0, len(new_keys) - len(to_embed)),
        )
