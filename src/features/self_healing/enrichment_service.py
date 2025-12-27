# src/features/self_healing/enrichment_service.py

"""Provides functionality for the enrichment_service module."""

from __future__ import annotations

from functools import partial
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from features.introspection.knowledge_helpers import extract_source_code
from shared.config import settings
from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.logger import getLogger
from shared.utils.parallel_processor import ThrottledParallelProcessor
from shared.utils.parsing import extract_json_from_response
from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)
REPO_ROOT = settings.REPO_PATH


async def _get_symbols_to_enrich(session: AsyncSession) -> list[dict[str, Any]]:
    """
    Fetches symbols that are ready for enrichment (have a null or placeholder description).

    Args:
        session: Database session (injected dependency)
    """
    result = await session.execute(
        text(
            """
            SELECT id, symbol_path, file_path, qualname
            FROM core.symbols
            WHERE intent IS NULL
               OR intent = 'Placeholder description'
               OR intent = ''
            ORDER BY symbol_path
            LIMIT 500
            """
        )
    )
    rows = result.fetchall()
    return [
        {
            "uuid": str(row.id),
            "symbol_path": row.symbol_path,
            "file_path": row.file_path,
            "qualname": row.qualname,
        }
        for row in rows
    ]


async def _enrich_single_symbol(
    symbol: dict[str, Any],
    cognitive_service: CognitiveService,
    qdrant_service: QdrantService,
) -> dict[str, str]:
    """
    Enriches a single symbol's description by using vector search + AI.

    Args:
        symbol: Symbol metadata dictionary
        cognitive_service: Service for AI interactions
        qdrant_service: Service for vector search
    """
    symbol_id = symbol["uuid"]
    symbol_path = symbol["symbol_path"]
    file_path = symbol.get("file_path", "")

    try:
        # Extract source code
        source_code = extract_source_code(file_path, symbol.get("qualname", ""))

        if not source_code:
            logger.warning("No source code found for %s", symbol_path)
            return {"uuid": symbol_id, "description": "error.no_source"}

        # Build context using vector search
        search_results = await qdrant_service.search(
            query_text=f"{symbol_path} {source_code[:500]}", limit=5
        )

        # Build prompt
        context_text = "\n".join(
            [
                f"- {r.payload.get('name', 'unknown')}: {r.payload.get('summary', '')}"
                for r in search_results
            ]
        )

        prompt = f"""Analyze this code and provide a concise description:

Symbol: {symbol_path}

Code:
```python
{source_code[:1000]}
```

Similar symbols:
{context_text}

Provide a one-sentence description of what this symbol does."""

        # Get AI description
        agent = await cognitive_service.aget_client_for_role("CodeReviewer")
        response = await agent.make_request_async(prompt, user_id="enrichment")

        # Extract description
        try:
            parsed = extract_json_from_response(response)
            if isinstance(parsed, dict):
                description = parsed.get("description", response.strip())
            else:
                description = response.strip()
        except Exception:
            description = response.strip()

        # Clean up description
        description = description.replace("\n", " ").strip()
        if len(description) > 500:
            description = description[:497] + "..."

        logger.info("✓ Enriched %s", symbol_path)
        return {"uuid": symbol_id, "description": description}

    except Exception as e:
        logger.error("Failed to enrich %s: %s", symbol_path, e)
        return {"uuid": symbol_id, "description": f"error.{type(e).__name__}"}


async def _update_descriptions_in_db(
    session: AsyncSession, descriptions: list[dict[str, str]]
):
    """
    Updates symbol descriptions in the database.

    Args:
        session: Database session (injected dependency)
        descriptions: List of {uuid, description} dicts to update
    """
    if not descriptions:
        return

    logger.info(
        "Attempting to update %s descriptions in the database...", len(descriptions)
    )

    async with session.begin():
        await session.execute(
            text("UPDATE core.symbols SET intent = :description WHERE id = :uuid"),
            descriptions,
        )

    logger.info("Database update transaction completed.")


# ID: 78078aae-3e69-4e5e-bd86-5c046a63314c
async def enrich_symbols(
    session: AsyncSession,
    cognitive_service: CognitiveService,
    qdrant_service: QdrantService,
    dry_run: bool,
):
    """
    The main orchestrator for the autonomous symbol enrichment process.

    Args:
        session: Database session (injected dependency)
        cognitive_service: Service for AI interactions
        qdrant_service: Service for vector search
        dry_run: If True, only report what would be done
    """
    symbols_to_enrich = await _get_symbols_to_enrich(session)

    if not symbols_to_enrich:
        logger.info("✅ No symbols with placeholder descriptions found.")
        return

    logger.info("   -> Found %s symbols to enrich...", len(symbols_to_enrich))

    processor = ThrottledParallelProcessor(description="Enriching symbols...")
    worker_fn = partial(
        _enrich_single_symbol,
        cognitive_service=cognitive_service,
        qdrant_service=qdrant_service,
    )
    descriptions = await processor.run_async(symbols_to_enrich, worker_fn)

    valid_descriptions = [
        d
        for d in descriptions
        if d.get("description") and (not d["description"].startswith("error."))
    ]

    if dry_run:
        logger.info("-- DRY RUN: The following descriptions would be written --")
        for d in valid_descriptions[:10]:
            logger.info("  - Symbol ID %s -> '%s'", d["uuid"], d["description"])
        if len(valid_descriptions) > 10:
            logger.info("  - ... and %s more.", len(valid_descriptions) - 10)
        return

    await _update_descriptions_in_db(session, valid_descriptions)
    logger.info(
        "   -> Successfully enriched %s symbols in the database.",
        len(valid_descriptions),
    )
