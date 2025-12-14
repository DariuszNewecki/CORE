# src/features/self_healing/capability_tagging_service.py

"""
Service logic for applying capability tags to untagged public symbols
via the CapabilityTaggerAgent.

This module is part of the FEATURES layer and therefore MUST NOT import
from body.cli.* or other higher layers.

Dependencies (ContextService, session factory, cognitive/knowledge services)
must be injected by the caller (CLI or fix workflow).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy import text

from shared.config import settings
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.logger import getLogger
from will.agents.tagger_agent import CapabilityTaggerAgent
from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)
REPO_ROOT = settings.REPO_PATH
SessionFactory = Callable[[], Any]


async def _async_tag_capabilities(
    cognitive_service: CognitiveService,
    knowledge_service: KnowledgeService,
    session_factory: SessionFactory,
    file_path: Path | None,
    dry_run: bool,
) -> None:
    """
    Core async logic for capability tagging.

    This function registers capability links in the DB using the injected session_factory.
    It NO LONGER writes # ID tags to source files (that is handled by 'fix ids').
    """
    agent = CapabilityTaggerAgent(cognitive_service, knowledge_service)
    suggestions = await agent.suggest_and_apply_tags(
        file_path=file_path.as_posix() if file_path else None
    )
    if not suggestions:
        logger.info("No new public capabilities to register.")
        return
    if dry_run:
        logger.info("-- DRY RUN: Would register the following capability links --")
        for key, info in suggestions.items():
            logger.info(
                "  • Symbol %s -> Capability '%s'", info["name"], info["suggestion"]
            )
        return
    logger.info(
        "Linking %s symbols to capabilities in the database...", len(suggestions)
    )
    async with session_factory() as session:
        async with session.begin():
            for _, new_info in suggestions.items():
                suggested_name = new_info["suggestion"]
                symbol_uuid = new_info["key"]
                domain = (
                    suggested_name.split(".")[0] if "." in suggested_name else "general"
                )
                cap_upsert_sql = text(
                    "\n                    INSERT INTO core.capabilities\n                        (name, domain, title, owner, status, tags, created_at, updated_at)\n                    VALUES\n                        (:name, :domain, :name, 'system', 'Active', '[]'::jsonb, now(), now())\n                    ON CONFLICT (domain, name)\n                    DO UPDATE SET updated_at = now()\n                    RETURNING id;\n                    "
                )
                result = await session.execute(
                    cap_upsert_sql, {"name": suggested_name, "domain": domain}
                )
                capability_id = result.scalar_one()
                link_sql = text(
                    "\n                    INSERT INTO core.symbol_capability_links\n                        (symbol_id, capability_id, confidence, source, verified, created_at)\n                    VALUES\n                        (:symbol_id, :capability_id, 1.0, 'llm-classified', true, now())\n                    ON CONFLICT (symbol_id, capability_id, source) DO NOTHING;\n                    "
                )
                await session.execute(
                    link_sql, {"symbol_id": symbol_uuid, "capability_id": capability_id}
                )
                logger.info("   → Linked '{new_info['name']}' to '%s'", suggested_name)
        await session.commit()


# ID: ba923fe1-b7d4-415c-8a96-40e0bed1e401
def main_sync(
    session_factory: SessionFactory,
    cognitive_service: CognitiveService,
    knowledge_service: KnowledgeService,
    write: bool = False,
    dry_run: bool = False,
) -> None:
    """Synchronous wrapper for capability tagging."""
    effective_dry_run = dry_run or not write
    asyncio.run(
        _async_tag_capabilities(
            cognitive_service=cognitive_service,
            knowledge_service=knowledge_service,
            session_factory=session_factory,
            file_path=None,
            dry_run=effective_dry_run,
        )
    )


# ID: 7f2a55a8-c88e-4ef9-a6e9-62849bc53837
async def main_async(
    session_factory: SessionFactory,
    cognitive_service: CognitiveService,
    knowledge_service: KnowledgeService,
    write: bool = False,
    dry_run: bool = False,
) -> None:
    """Async wrapper used by `fix all` workflows."""
    effective_dry_run = dry_run or not write
    await _async_tag_capabilities(
        cognitive_service=cognitive_service,
        knowledge_service=knowledge_service,
        session_factory=session_factory,
        file_path=None,
        dry_run=effective_dry_run,
    )
