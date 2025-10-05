# src/features/project_lifecycle/definition_service.py
from __future__ import annotations

import asyncio
import re
from functools import partial
from typing import Any, Dict, List, Set

from core.cognitive_service import CognitiveService
from rich.console import Console
from services.clients.qdrant_client import QdrantService
from services.database.session_manager import get_session
from shared.config import settings
from shared.logger import getLogger
from shared.utils.parallel_processor import ThrottledParallelProcessor
from sqlalchemy import text

from features.introspection.knowledge_helpers import extract_source_code

console = Console()
log = getLogger("definition_service")


# ID: e8474497-40b5-47df-8480-602bfa03aaf8
async def get_undefined_symbols() -> List[Dict[str, Any]]:
    """
    Fetches symbols that are ready for definition (have a vector_id but no key).
    """
    async with get_session() as session:
        result = await session.execute(
            text(
                """
                SELECT id, symbol_path, module AS file_path, vector_id
                FROM core.symbols
                WHERE key IS NULL AND vector_id IS NOT NULL
                """
            )
        )
        return [dict(row._mapping) for row in result]


# ID: f30f4ec0-3ed3-4775-b018-28be18692ebf
async def define_single_symbol(
    symbol: Dict[str, Any],
    cognitive_service: CognitiveService,
    qdrant_service: QdrantService,
    existing_keys: Set[str],
) -> Dict[str, Any]:
    """Uses an AI to generate a definition for a single symbol, using semantic context."""
    log.info(f"Defining symbol: {symbol.get('symbol_path')}")
    source_code = extract_source_code(settings.REPO_PATH, symbol)
    if not source_code:
        return {"id": symbol["id"], "key": "error.code_not_found"}

    similar_capabilities_str = "No similar capabilities found."
    vector_id = symbol.get("vector_id")
    if vector_id:
        try:
            vector = await qdrant_service.get_vector_by_id(vector_id)
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
            log.warning(
                f"Semantic search failed during definition for {symbol['symbol_path']}: {e}"
            )

    prompt_template = (
        "Analyze the following code and propose a structured, dot-notation capability key (e.g., domain.subdomain.action).\n"
        "CONTEXT: {similar_capabilities}\n\n"
        "```python\n{code}\n```\n\n"
        "Respond with ONLY the key."
    )
    final_prompt = prompt_template.format(
        code=source_code, similar_capabilities=similar_capabilities_str
    )

    definer_agent = await cognitive_service.aget_client_for_role("CodeReviewer")
    raw_suggested_key = await definer_agent.make_request_async(
        final_prompt, user_id="definer_agent"
    )

    match = re.search(r"`(.*?)`", raw_suggested_key)
    suggested_key = match.group(1) if match else raw_suggested_key
    suggested_key = suggested_key.strip()

    if suggested_key in existing_keys:
        console.print(
            f"[yellow]Warning: AI suggested existing key '{suggested_key}' for a new symbol. Skipping to avoid conflict.[/yellow]"
        )
        return {"id": symbol["id"], "key": "error.duplicate_key"}

    try:
        delay_str = settings.model_extra.get("LLM_SECONDS_BETWEEN_REQUESTS", "1")
        delay = int(delay_str)
    except (ValueError, TypeError):
        delay = 1
    await asyncio.sleep(delay)

    return {"id": symbol["id"], "key": suggested_key}


# ID: 1c642222-6e05-4e31-a9f6-68502a054947
async def update_definitions_in_db(definitions: List[Dict[str, Any]]):
    """Updates the 'key' column for symbols in the database."""
    if not definitions:
        return

    log.info(f"Attempting to update {len(definitions)} definitions in the database...")
    async with get_session() as session:
        async with session.begin():
            await session.execute(
                text("UPDATE core.symbols SET key = :key WHERE id = :id"),
                definitions,
            )
    log.info("Database update transaction completed.")


# ID: 073b8012-385d-4c2b-972e-0e6914fe0d30
async def define_new_symbols(cognitive_service: CognitiveService):
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

    qdrant_service = QdrantService()
    processor = ThrottledParallelProcessor(description="Defining symbols...")
    worker_fn = partial(
        define_single_symbol,
        cognitive_service=cognitive_service,
        qdrant_service=qdrant_service,
        existing_keys=existing_keys,
    )
    definitions = await processor.run_async(undefined_symbols, worker_fn)

    valid_definitions = [
        d for d in definitions if d.get("key") and not d["key"].startswith("error.")
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
