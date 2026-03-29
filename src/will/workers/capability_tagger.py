# src/will/workers/capability_tagger.py
"""
Capability Tagger Worker - Constitutional Sensing Worker.

Responsibility: Query the knowledge graph for public symbols with no
capability key assigned, invoke the CapabilityTaggerAgent to generate
LLM-powered suggestions, persist them to the database, and post a
completion report to the Blackboard.

Constitutional standing:
- Declaration:      .intent/workers/capability_tagger.yaml
- Class:            sensing
- Phase:            audit
- Permitted tools:  llm.local
- Approval:         false

LAYER: will/workers - sensing worker. Reads DB symbols, writes capability
keys back to DB. No src/ writes. No file mutations.
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

_BATCH_SIZE = 20


# ID: e1f2a3b4-c5d6-7890-efab-cd1234567890
class CapabilityTaggerWorker(Worker):
    """
    Sensing worker. Finds public symbols with no capability key assigned,
    uses CapabilityTaggerAgent to generate LLM-powered suggestions,
    and persists the assignments to the database.

    Processes symbols in batches of _BATCH_SIZE per cycle to avoid
    overwhelming the local LLM. Picks up where it left off on the
    next cycle via the key IS NULL condition.

    approval_required: false - writes capability keys to DB only.
    """

    declaration_name = "capability_tagger"

    def __init__(self, cognitive_service: Any = None) -> None:
        from shared.infrastructure.bootstrap_registry import BootstrapRegistry

        super().__init__()
        self._cognitive_service = cognitive_service
        self._repo_root = BootstrapRegistry.get_repo_path()

    # ID: f2a3b4c5-d6e7-8901-fabc-de2345678901
    async def run(self) -> None:
        """
        One tagging cycle:
        1. Post heartbeat.
        2. Fetch untagged public symbols from DB.
        3. Invoke CapabilityTaggerAgent for suggestions.
        4. Persist capability keys to DB.
        5. Post completion report to Blackboard.
        """
        await self.post_heartbeat()

        if self._cognitive_service is None:
            await self.post_report(
                subject="capability_tagger.run.complete",
                payload={"tagged": 0, "reason": "cognitive_service_unavailable"},
            )
            return

        untagged = await self._fetch_untagged_symbols()

        if not untagged:
            await self.post_report(
                subject="capability_tagger.run.complete",
                payload={
                    "tagged": 0,
                    "message": "All public symbols have capability keys.",
                },
            )
            logger.info("CapabilityTaggerWorker: nothing to tag.")
            return

        logger.info(
            "CapabilityTaggerWorker: %d untagged symbols to process (batch=%d)",
            len(untagged),
            _BATCH_SIZE,
        )

        tagged = await self._tag_symbols(untagged)

        await self.post_report(
            subject="capability_tagger.run.complete",
            payload={
                "tagged": tagged,
                "processed": len(untagged),
            },
        )
        logger.info("CapabilityTaggerWorker: cycle complete — tagged=%d", tagged)

    async def _fetch_untagged_symbols(self) -> list[dict]:
        """Fetch public symbols with no capability key, ordered by symbol_path."""
        from body.services.service_registry import service_registry

        svc = await service_registry.get_symbol_service()
        return await svc.fetch_untagged_symbols(_BATCH_SIZE)

    async def _tag_symbols(self, symbols: list[dict]) -> int:
        """
        Invoke CapabilityTaggerAgent and persist results.
        Returns count of successfully tagged symbols.
        """
        from body.services.service_registry import service_registry
        from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
        from will.agents.capability_tagger_agent import CapabilityTaggerAgent

        knowledge_service = KnowledgeService(self._repo_root)
        agent = CapabilityTaggerAgent(
            cognitive_service=self._cognitive_service,
            knowledge_service=knowledge_service,
        )

        suggestions = await agent.suggest_and_apply_tags(limit=_BATCH_SIZE)

        if not suggestions:
            return 0

        assignments = []
        for _key, info in suggestions.items():
            symbol_uuid = info.get("key")
            suggested_key = str(info.get("suggestion", "")).strip()

            if not symbol_uuid or not suggested_key or "." not in suggested_key:
                continue

            assignments.append({"id": symbol_uuid, "key": suggested_key})
            logger.debug(
                "CapabilityTaggerWorker: %s -> %s",
                info.get("name"),
                suggested_key,
            )

        if assignments:
            svc = await service_registry.get_symbol_service()
            await svc.apply_symbol_keys(assignments)

        return len(assignments)
