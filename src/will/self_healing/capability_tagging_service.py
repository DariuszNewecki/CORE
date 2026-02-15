# src/features/self_healing/capability_tagging_service.py

"""
Service logic for applying capability tags to untagged public symbols
via the CapabilityTaggerAgent.

Constitutional rules enforced:
- LLMs MAY propose capability names and metadata.
- LLMs MUST NOT assign top-level domains (domains are SSOT-governed).
- LLM outputs MUST NOT be persisted as 'verified'.
- `subdomain` is treated as a non-authoritative namespace only.

This service performs the DB-level registration of proposed capabilities.
The actual writing of '# ID:' tags to source files is handled by 'fix ids'.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy import text

from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.logger import getLogger
from will.agents.tagger_agent import CapabilityTaggerAgent
from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)
SessionFactory = Callable[[], Any]

# Constitutional holding domain for non-SSOT capability registrations.
# Anything created here is explicitly "Proposed" and must be governed later.
HOLDING_DOMAIN = "general"

# Links created by LLM are proposals until explicitly verified by a governed flow.
LLM_LINK_SOURCE = "llm-proposed"
DEFAULT_LLM_CONFIDENCE = 0.70


def _split_capability_key(suggested_name: str) -> tuple[str | None, str | None]:
    """
    Split an LLM-suggested capability key into (proposed_domain, namespace).

    IMPORTANT:
    - proposed_domain is NOT authoritative (top-level domains are SSOT-governed).
    - namespace is advisory only and MUST NOT be used as an authority boundary.
    """
    key = (suggested_name or "").strip()
    if "." not in key:
        return None, None
    proposed_domain, namespace = key.split(".", 1)
    proposed_domain = proposed_domain.strip() or None
    namespace = namespace.strip() or None
    return proposed_domain, namespace


def _proposed_domain_tag(suggested_name: str) -> str | None:
    """Extract a proposed domain tag for metadata tracking."""
    proposed_domain, _ = _split_capability_key(suggested_name)
    if not proposed_domain:
        return None
    return f"proposed_domain:{proposed_domain}"


def _proposed_namespace_tag(suggested_name: str) -> str | None:
    """Extract a proposed namespace tag for metadata tracking."""
    _, namespace = _split_capability_key(suggested_name)
    if not namespace:
        return None
    return f"proposed_namespace:{namespace}"


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
    """
    # 1. Consult the Will (Agent) to get suggestions
    agent = CapabilityTaggerAgent(cognitive_service, knowledge_service)
    suggestions = await agent.suggest_and_apply_tags(
        file_path=file_path.as_posix() if file_path else None
    )

    if not suggestions:
        logger.info("✅ No new public capabilities to register.")
        return

    if dry_run:
        logger.info("-- DRY RUN: The following capability links would be proposed --")
        for _, info in suggestions.items():
            logger.info(
                "  • Symbol %s -> Capability '%s'", info["name"], info["suggestion"]
            )
        return

    logger.info(
        "Registering %s LLM capability proposals in the database...", len(suggestions)
    )

    # 2. Execute the Body operation (Database Persistence)
    async with session_factory() as session:
        # Use an explicit transaction boundary
        async with session.begin():
            for _, new_info in suggestions.items():
                suggested_name = str(new_info["suggestion"]).strip()
                symbol_uuid = new_info["key"]

                # DOMAIN PROTECTION: Force all LLM suggestions into the holding domain.
                domain = HOLDING_DOMAIN

                # Extract advisory namespace (informational only)
                _, namespace = _split_capability_key(suggested_name)

                # Build metadata tags
                tags: list[str] = []
                proposed_domain = _proposed_domain_tag(suggested_name)
                if proposed_domain:
                    tags.append(proposed_domain)
                proposed_namespace = _proposed_namespace_tag(suggested_name)
                if proposed_namespace:
                    tags.append(proposed_namespace)

                confidence = float(new_info.get("confidence", DEFAULT_LLM_CONFIDENCE))

                # Upsert the capability as a 'Proposed' entity
                cap_upsert_sql = text(
                    """
                    INSERT INTO core.capabilities
                        (name, domain, subdomain, title, owner, status, tags, created_at, updated_at)
                    VALUES
                        (:name, :domain, :subdomain, :title, 'system', 'Proposed', :tags::jsonb, now(), now())
                    ON CONFLICT (domain, name)
                    DO UPDATE SET
                        updated_at = now(),
                        status = 'Proposed',
                        subdomain = COALESCE(EXCLUDED.subdomain, core.capabilities.subdomain),
                        tags = CASE
                            WHEN core.capabilities.tags IS NULL THEN :tags::jsonb
                            ELSE core.capabilities.tags || :tags::jsonb
                        END
                    RETURNING id;
                    """
                )

                result = await session.execute(
                    cap_upsert_sql,
                    {
                        "name": suggested_name,
                        "domain": domain,
                        "subdomain": namespace,
                        "title": suggested_name,
                        "tags": json.dumps(tags),
                    },
                )
                capability_id = result.scalar_one()

                # Link the symbol to the proposed capability
                link_sql = text(
                    """
                    INSERT INTO core.symbol_capability_links
                        (symbol_id, capability_id, confidence, source, verified, created_at)
                    VALUES
                        (:symbol_id, :capability_id, :confidence, :source, false, now())
                    ON CONFLICT (symbol_id, capability_id, source) DO NOTHING;
                    """
                )

                await session.execute(
                    link_sql,
                    {
                        "symbol_id": symbol_uuid,
                        "capability_id": capability_id,
                        "confidence": confidence,
                        "source": LLM_LINK_SOURCE,
                    },
                )

                logger.info(
                    "   → ✅ Registered proposal: '%s' linked to '%s'",
                    new_info["name"],
                    suggested_name,
                )


# ID: ba923fe1-b7d4-415c-8a96-40e0bed1e401
async def main_async(
    session_factory: SessionFactory,
    cognitive_service: CognitiveService,
    knowledge_service: KnowledgeService,
    write: bool = False,
    dry_run: bool = False,
) -> None:
    """
    Entry point for the capability tagging service.

    Args:
        session_factory: Factory to create async DB sessions.
        cognitive_service: Initialized cognitive service.
        knowledge_service: Initialized knowledge service.
        write: True if changes should be persisted.
        dry_run: True if changes should only be simulated.
    """
    # Calculate effective dry run status
    effective_dry_run = dry_run or not write

    await _async_tag_capabilities(
        cognitive_service=cognitive_service,
        knowledge_service=knowledge_service,
        session_factory=session_factory,
        file_path=None,
        dry_run=effective_dry_run,
    )
