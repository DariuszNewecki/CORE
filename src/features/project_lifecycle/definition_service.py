# src/features/project_lifecycle/definition_service.py

"""Provides functionality for the definition_service module."""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Any

from rich.console import Console
from services.clients.qdrant_client import QdrantService
from services.database.session_manager import get_session
from shared.config import settings
from shared.logger import getLogger
from shared.utils.parallel_processor import ThrottledParallelProcessor
from sqlalchemy import text
from will.orchestration.cognitive_service import CognitiveService

from features.introspection.knowledge_helpers import extract_source_code

console = Console()
logger = getLogger(__name__)


# ID: 45733c48-d1d4-4e44-8e06-af55a656e585
async def get_undefined_symbols() -> list[dict[str, Any]]:
    """
    Fetches symbols that are ready for definition (have a vector link but no key).
    """
    async with get_session() as session:
        result = await session.execute(
            text(
                "\n                SELECT s.id, s.symbol_path, s.module, vl.vector_id\n                FROM core.symbols s\n                JOIN core.symbol_vector_links vl ON s.id = vl.symbol_id\n                WHERE s.key IS NULL\n                "
            )
        )
        return [dict(row._mapping) for row in result]


# ID: dd8e26e5-d606-42bf-89f2-36866461c0fe
async def define_single_symbol(
    symbol: dict[str, Any],
    cognitive_service: CognitiveService,
    qdrant_service: QdrantService,
    existing_keys: set[str],
) -> dict[str, Any]:
    """Uses an AI to generate a definition for a single symbol, using semantic context."""
    logger.info(f"Defining symbol: {symbol.get('symbol_path')}")
    source_code = extract_source_code(settings.REPO_PATH, symbol)
    if not source_code:
        logger.warning(
            f"Cannot extract source code for {symbol.get('symbol_path')}: symbol data is likely missing 'module' or 'symbol_path'."
        )
        return {"id": symbol["id"], "key": "error.code_not_found"}
    similar_capabilities_str = "No similar capabilities found."
    vector_id = symbol.get("vector_id")
    if vector_id:
        try:
            vector = await qdrant_service.get_vector_by_id(str(vector_id))
            if vector:
                similar_hits = await qdrant_service.search_similar(vector, limit=3)
                similar_keys = [
                    hit["payload"]["chunk_id"]
                    for hit in similar_hits
                    if hit.get("payload")
                ]
                if similar_keys:
                    similar_capabilities_str = (
                        "Found similar existing capabilities: "
                        + ", ".join(f"`{k}`" for k in similar_keys)
                    )
        except Exception as e:
            logger.warning(
                f"Semantic search failed during definition for {symbol['symbol_path']}: {e}"
            )
    prompt_template_path = settings.get_path("mind.prompts.capability_definer")
    prompt_template = prompt_template_path.read_text(encoding="utf-8")
    final_prompt = prompt_template.format(
        code=source_code, similar_capabilities=similar_capabilities_str
    )
    definer_agent = await cognitive_service.aget_client_for_role("CodeReviewer")
    raw_suggested_key = await definer_agent.make_request_async(
        final_prompt, user_id="definer_agent"
    )
    cleaned_key = (
        raw_suggested_key.strip().replace("`", "").replace("'", "").replace('"', "")
    )
    if cleaned_key in existing_keys:
        console.print(
            f"[yellow]Warning: AI suggested existing key '{cleaned_key}' for a new symbol. Skipping to avoid conflict.[/yellow]"
        )
        return {"id": symbol["id"], "key": "error.duplicate_key"}
    try:
        delay_str = settings.model_extra.get("LLM_SECONDS_BETWEEN_REQUESTS", "1")
        delay = int(delay_str)
    except (ValueError, TypeError):
        delay = 1
    await asyncio.sleep(delay)
    return {"id": symbol["id"], "key": cleaned_key}


# ID: 3a986e52-f145-414c-9dee-dea773df5d8c
async def update_definitions_in_db(definitions: list[dict[str, Any]]):
    """Updates the 'key' column for symbols in the database."""
    if not definitions:
        return
    logger.info(
        f"Attempting to update {len(definitions)} definitions in the database..."
    )
    serializable_definitions = [
        {"id": str(d["id"]), "key": d["key"]} for d in definitions
    ]
    async with get_session() as session:
        async with session.begin():
            await session.execute(
                text("UPDATE core.symbols SET key = :key WHERE id = :id"),
                serializable_definitions,
            )
    logger.info("Database update transaction completed.")


# ID: 6da20d3b-243c-466c-9b03-d3f28ed95045
async def define_new_symbols(
    cognitive_service: CognitiveService, qdrant_service: QdrantService
):
    """The main orchestrator for the autonomous definition process."""
    undefined_symbols = await get_undefined_symbols()
    if not undefined_symbols:
        console.print("   -> No new symbols to define.")
        return
    async with get_session() as session:
        result = await session.execute(
            text("SELECT key FROM core.symbols WHERE key IS NOT NULL")
        )
        existing_keys = {row[0] for row in result}
    console.print(f"   -> Found {len(undefined_symbols)} new symbols to define...")
    processor = ThrottledParallelProcessor(description="Defining symbols...")
    worker_fn = partial(
        define_single_symbol,
        cognitive_service=cognitive_service,
        qdrant_service=qdrant_service,
        existing_keys=existing_keys,
    )
    definitions = await processor.run_async(undefined_symbols, worker_fn)
    valid_definitions = [
        d for d in definitions if d.get("key") and (not d["key"].startswith("error."))
    ]
    unique_definitions = []
    seen_keys = set()
    for d in valid_definitions:
        key = d["key"]
        if key not in seen_keys:
            unique_definitions.append(d)
            seen_keys.add(key)
        else:
            console.print(
                f"[yellow]Warning: AI generated duplicate key '{key}'. Skipping redundant assignment.[/yellow]"
            )
    await update_definitions_in_db(unique_definitions)
    console.print(
        f"   -> Successfully defined {len(unique_definitions)} new capabilities."
    )
