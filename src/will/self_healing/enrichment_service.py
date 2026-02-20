# src/will/self_healing/enrichment_service.py

"""
Symbol Enrichment Service

This module:
- Finds symbols in the DB that have placeholder or missing descriptions.
- Uses an LLM role to generate concise descriptions.
- Writes enriched descriptions back to the database.

Change rationale (Dec 2025):
- 'core-admin enrich symbols' should use the DB-defined cognitive role 'LocalCoder'
  (mapped to your local Ollama model) instead of the generic 'CodeReviewer'.

NOTE:
- This file assumes QdrantService exposes a best-effort code lookup method.
  If your adapter uses a different method name or payload schema, adjust
  _fetch_code_for_symbol() accordingly.
"""

from __future__ import annotations

from functools import partial
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.infrastructure.config_service import ConfigService
from shared.logger import getLogger
from shared.utils.parallel_processor import ThrottledParallelProcessor
from shared.utils.parsing import extract_json_from_response
from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)

# Role used for "core-admin enrich symbols" (DB-driven role -> resource mapping)
ENRICH_SYMBOLS_ROLE = "LocalCoder"


async def _get_symbols_to_enrich(session: AsyncSession) -> list[dict[str, Any]]:
    """Fetch symbols that are ready for enrichment.

    Criteria:
      - intent is NULL, empty, or a known placeholder.

    NOTE:
      - This is intentionally conservative: it avoids overwriting real intent.
      - Tune patterns or LIMIT if you want broader enrichment runs.
    """

    stmt = text(
        """
        SELECT id::text AS uuid, symbol_path
        FROM core.symbols
        WHERE intent IS NULL
           OR btrim(intent) = ''
           OR intent ILIKE 'todo%'
           OR intent ILIKE 'tbd%'
           OR intent ILIKE 'placeholder%'
        ORDER BY updated_at NULLS FIRST, created_at
        LIMIT 200
        """
    )

    result = await session.execute(stmt)
    rows = result.mappings().all()
    return [dict(r) for r in rows]


def _build_prompt(symbol_path: str, source_code: str) -> str:
    """Build the enrichment prompt."""
    return f"""Analyze this Python code and provide a concise one-sentence description of its purpose.
Symbol: {symbol_path}
Code:
```python
{source_code}
```
Response Requirement:
Return a JSON object: {{"description": "Your one-sentence description here"}}
"""


async def _fetch_code_for_symbol(
    qdrant_service: QdrantService, symbol_path: str
) -> str:
    """Fetch code context for a symbol (best-effort).

    This should return a relevant code snippet for the given symbol_path.

    If Qdrant doesn't have it (or the lookup fails), returns an empty string.
    """

    try:
        # IMPORTANT:
        # Replace with your project's actual Qdrant lookup method if different.
        result = await qdrant_service.search_code(symbol_path, limit=1)
        if not result:
            return ""

        top = result[0]
        payload = getattr(top, "payload", None) or {}

        # Try common payload keys used in code vectorization pipelines.
        code = payload.get("code") or payload.get("source") or payload.get("text") or ""
        return str(code)

    except Exception:
        return ""


async def _enrich_single_symbol(
    symbol: dict[str, Any],
    cognitive_service: CognitiveService,
    qdrant_service: QdrantService,
) -> dict[str, str]:
    """Enrich a single symbol with a description."""

    symbol_id = str(symbol.get("uuid", "")).strip()
    symbol_path = str(symbol.get("symbol_path", "")).strip()

    if not symbol_id or not symbol_path:
        return {"uuid": symbol_id or "", "description": "error.invalid_symbol"}

    try:
        code = await _fetch_code_for_symbol(qdrant_service, symbol_path)
        prompt = _build_prompt(symbol_path, code)

        # DB-mapped role: LocalCoder -> your local Ollama model resource
        agent = await cognitive_service.aget_client_for_role(ENRICH_SYMBOLS_ROLE)
        response = await agent.make_request_async(prompt, user_id="enrichment")

        description = ""

        # Prefer structured JSON response.
        try:
            parsed = extract_json_from_response(response)
            if isinstance(parsed, dict):
                description = str(parsed.get("description", "")).strip()
        except Exception:
            description = ""

        # Fallback: first line of text.
        if not description:
            description = (response or "").strip().split("\n")[0]

        description = description.replace("\n", " ").strip()
        if len(description) > 500:
            description = description[:497] + "..."

        logger.info("✓ Enriched %s", symbol_path)
        return {"uuid": symbol_id, "description": description}

    except Exception as exc:
        logger.error("Failed to enrich %s: %s", symbol_path, exc)
        return {"uuid": symbol_id, "description": f"error.{type(exc).__name__}"}


async def _update_descriptions_in_db(
    session: AsyncSession,
    descriptions: list[dict[str, str]],
) -> None:
    """Update symbol `intent` descriptions in the database."""

    if not descriptions:
        return

    logger.info("Applying %s enriched descriptions to DB...", len(descriptions))

    # NOTE: Avoid PostgreSQL '::uuid' cast with named parameters; asyncpg will not parse
    # ':uuid::uuid' as a bind parameter. Use CAST(:uuid AS uuid) instead.
    stmt = text(
        "UPDATE core.symbols SET intent = :description WHERE id = CAST(:uuid AS uuid)"
    )

    await session.execute(stmt, descriptions)
    await session.commit()


# ID: 78078aae-3e69-4e5e-bd86-5c046a63314c
async def enrich_symbols(
    session: AsyncSession,
    cognitive_service: CognitiveService,
    qdrant_service: QdrantService,
    dry_run: bool,
    config_service: ConfigService | None = None,
) -> None:
    """Main orchestrator for autonomous symbol enrichment."""

    symbols_to_enrich = await _get_symbols_to_enrich(session)

    if not symbols_to_enrich:
        logger.info("✅ No symbols needing enrichment found.")
        return

    logger.info(
        "🔍 Found %s symbols with placeholder descriptions.", len(symbols_to_enrich)
    )

    processor = ThrottledParallelProcessor(description="Enriching symbols...")

    worker_fn = partial(
        _enrich_single_symbol,
        cognitive_service=cognitive_service,
        qdrant_service=qdrant_service,
    )

    results = await processor.run_async(symbols_to_enrich, worker_fn)

    valid_results = [
        r
        for r in (results or [])
        if r.get("description") and not str(r["description"]).startswith("error.")
    ]

    if dry_run:
        logger.info("-- DRY RUN: The following descriptions would be written --")
        for d in valid_results[:5]:
            logger.info("  - %s: %s", d["uuid"], d["description"])
        return

    if valid_results:
        await _update_descriptions_in_db(session, valid_results)
        logger.info("✅ Successfully updated %s symbols.", len(valid_results))
