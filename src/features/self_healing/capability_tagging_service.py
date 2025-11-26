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

from rich.console import Console
from services.knowledge.knowledge_service import KnowledgeService
from shared.config import settings
from shared.logger import getLogger
from sqlalchemy import text
from will.agents.tagger_agent import CapabilityTaggerAgent
from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)
console = Console()
REPO_ROOT = settings.REPO_PATH

# Async DB session factory type
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
        console.print(
            "[bold green]No new public capabilities to register.[/bold green]"
        )
        return

    # DRY RUN
    if dry_run:
        console.print(
            "[bold yellow]-- DRY RUN: Would register the following capability links --[/bold yellow]"
        )
        for key, info in suggestions.items():
            console.print(
                f"  • Symbol {info['name']} -> Capability '{info['suggestion']}'"
            )
        return

    console.print(
        f"\n[bold green]Linking {len(suggestions)} symbols to capabilities in the database...[/bold green]"
    )

    # ------------- DB OPERATION THROUGH INJECTED SESSION ---------------- #
    async with session_factory() as session:
        async with session.begin():
            for _, new_info in suggestions.items():
                suggested_name = new_info["suggestion"]
                symbol_uuid = new_info["key"]  # Use the existing ID from the symbol

                # ---------------- Register Capability ----------------------- #
                domain = (
                    suggested_name.split(".")[0] if "." in suggested_name else "general"
                )

                # Upsert capability and get its ID
                cap_upsert_sql = text(
                    """
                    INSERT INTO core.capabilities
                        (name, domain, title, owner, status, tags, created_at, updated_at)
                    VALUES
                        (:name, :domain, :name, 'system', 'Active', '[]'::jsonb, now(), now())
                    ON CONFLICT (domain, name)
                    DO UPDATE SET updated_at = now()
                    RETURNING id;
                    """
                )

                result = await session.execute(
                    cap_upsert_sql,
                    {"name": suggested_name, "domain": domain},
                )
                capability_id = result.scalar_one()

                # ---------------- Link Symbol to Capability ---------------- #
                # This replaces the old 'entry_points' array update
                link_sql = text(
                    """
                    INSERT INTO core.symbol_capability_links
                        (symbol_id, capability_id, confidence, source, verified, created_at)
                    VALUES
                        (:symbol_id, :capability_id, 1.0, 'llm-classified', true, now())
                    ON CONFLICT (symbol_id, capability_id, source) DO NOTHING;
                    """
                )

                await session.execute(
                    link_sql,
                    {"symbol_id": symbol_uuid, "capability_id": capability_id},
                )

                console.print(f"   → Linked '{new_info['name']}' to '{suggested_name}'")

        await session.commit()


# ------------------------------------------------------------------------------
# EXTERNAL PUBLIC ENTRYPOINTS — used by CLI / fix workflows
# ------------------------------------------------------------------------------


# ID: 7216f125-bffe-4e4a-9d0a-2596e9e864bb
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


# ID: 528c806f-ba48-4153-8864-7c1ff270e710
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
