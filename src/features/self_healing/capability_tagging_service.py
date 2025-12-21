# src/features/self_healing/capability_tagging_service.py

"""
Service logic for applying capability tags to untagged public symbols
via the CapabilityTaggerAgent.

Constitutional rule enforced here:
- LLMs MAY propose capability names and metadata
- LLMs MUST NOT assign top-level domains (domains are SSOT-governed)
- LLM outputs MUST NOT be persisted as 'verified'
- `subdomain` is treated as a non-authoritative namespace only

This module is part of the FEATURES layer and therefore MUST NOT import
from body.cli.* or other higher layers.

Dependencies (ContextService, session factory, cognitive/knowledge services)
must be injected by the caller (CLI or fix workflow).
"""

from __future__ import annotations

import json
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
    """
    Extract a *proposed* domain from an LLM-suggested capability key, without
    granting it authority.

    Example:
        enforcement.import_rules  -> "proposed_domain:enforcement"
    """
    proposed_domain, _ = _split_capability_key(suggested_name)
    if not proposed_domain:
        return None
    return f"proposed_domain:{proposed_domain}"


def _proposed_namespace_tag(suggested_name: str) -> str | None:
    """
    Extract a *proposed* namespace from an LLM-suggested capability key, without
    granting it authority.

    Example:
        enforcement.import_rules  -> "proposed_namespace:import_rules"
    """
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
    It NO LONGER writes # ID tags to source files (that is handled by 'fix ids').

    Constitutional guarantees:
    - No LLM output is persisted as an authoritative domain.
    - `subdomain` is treated as an advisory namespace only.
    - No LLM-created link is persisted as 'verified'.
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
        for _, info in suggestions.items():
            logger.info(
                "  • Symbol %s -> Capability '%s'", info["name"], info["suggestion"]
            )
        return

    logger.info(
        "Registering %s LLM capability proposals in the database...", len(suggestions)
    )

    async with session_factory() as session:
        # Transaction boundary lives here; session.begin() commits on success automatically.
        async with session.begin():
            for _, new_info in suggestions.items():
                suggested_name = str(new_info["suggestion"]).strip()
                symbol_uuid = new_info["key"]

                # Domain is SSOT-governed: do NOT derive it from LLM output.
                # All LLM-created capabilities land in a controlled holding domain.
                domain = HOLDING_DOMAIN

                # Extract advisory namespace (stored in DB column `subdomain`).
                # This is NOT an authority boundary.
                _, namespace = _split_capability_key(suggested_name)

                # Preserve LLM-implied domain/namespace as *non-authoritative* metadata only.
                tags: list[str] = []
                proposed_domain = _proposed_domain_tag(suggested_name)
                if proposed_domain:
                    tags.append(proposed_domain)
                proposed_namespace = _proposed_namespace_tag(suggested_name)
                if proposed_namespace:
                    tags.append(proposed_namespace)

                confidence = float(new_info.get("confidence", DEFAULT_LLM_CONFIDENCE))

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
                    "   → Proposed link '%s' -> '%s' (domain=%s, namespace=%s)",
                    new_info["name"],
                    suggested_name,
                    domain,
                    namespace,
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
    Async wrapper used by governed workflows.

    NOTE:
    - FEATURES layer does not start event loops.
    - If a synchronous CLI needs to invoke this, the sync runner must live in Body/CLI.
    """
    effective_dry_run = dry_run or not write
    await _async_tag_capabilities(
        cognitive_service=cognitive_service,
        knowledge_service=knowledge_service,
        session_factory=session_factory,
        file_path=None,
        dry_run=effective_dry_run,
    )
