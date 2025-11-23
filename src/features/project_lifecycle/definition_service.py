# src/features/project_lifecycle/definition_service.py

"""Provides functionality for the definition_service module."""

from __future__ import annotations

import re
from functools import partial
from typing import Any

from rich.console import Console
from sqlalchemy import text

from services.context import ContextService
from services.database.session_manager import get_session
from shared.config import settings
from shared.logger import getLogger
from shared.utils.parallel_processor import ThrottledParallelProcessor

console = Console()
logger = getLogger(__name__)


# ID: 45733c48-d1d4-4e44-8e06-af55a656e585
async def get_undefined_symbols() -> list[dict[str, Any]]:
    """
    Fetches symbols that are ready for definition (public and have no key).
    """
    async with get_session() as session:
        # --- START OF FIX: Changed JOIN to LEFT JOIN ---
        # This ensures we select all public, un-keyed symbols, regardless of
        # whether they have a vector link yet.
        result = await session.execute(
            text(
                """
                SELECT s.id, s.symbol_path, s.qualname, s.module, vl.vector_id
                FROM core.symbols s
                LEFT JOIN core.symbol_vector_links vl ON s.id = vl.symbol_id
                WHERE s.key IS NULL AND s.is_public = TRUE
                """
            )
        )
        # --- END OF FIX ---
        return [dict(row._mapping) for row in result]


# ID: dd8e26e5-d606-42bf-89f2-36866461c0fe
async def define_single_symbol(
    symbol: dict[str, Any],
    context_service: ContextService,
    existing_keys: set[str],
) -> dict[str, Any]:
    """Uses an AI to generate a definition for a single symbol, using semantic context."""
    logger.info(f"Defining symbol: {symbol.get('symbol_path')}")

    symbol_path = symbol.get("symbol_path", "")
    file_path, symbol_name = (
        symbol_path.split("::", 1) if "::" in symbol_path else (symbol_path, "")
    )

    task_spec = {
        "task_id": f"define-{symbol['id']}",
        "task_type": "refactor",
        "summary": f"Define a capability key for the symbol {symbol_path}",
        "target_file": file_path,
        "target_symbol": symbol_name,
        "scope": {"traversal_depth": 1},
        "constraints": {"max_items": 10},
    }

    try:
        packet = await context_service.build_for_task(task_spec, use_cache=False)
        source_code = ""
        similar_capabilities_str = "No similar capabilities found."

        similar_keys = []
        target_simple_name = symbol.get("qualname", "").split(".")[-1]

        for item in packet.get("context", []):
            if (
                item.get("item_type") == "code"
                and item.get("name") == target_simple_name
            ):
                source_code = item.get("content", "")
            elif item.get("item_type") == "symbol":
                if item.get("name") != symbol.get("qualname"):
                    similar_keys.append(item.get("name", ""))

        if not source_code:
            logger.warning(
                f"Could not find source code in context packet for {symbol['symbol_path']}"
            )
            return {"id": symbol["id"], "key": "error.code_not_found"}

        if similar_keys:
            similar_capabilities_str = (
                "Found similar existing capabilities: "
                + ", ".join(f"`{k}`" for k in similar_keys)
            )

        prompt_template_path = settings.get_path("mind.prompts.capability_definer")
        prompt_template = prompt_template_path.read_text(encoding="utf-8")
        final_prompt = prompt_template.format(
            code=source_code, similar_capabilities=similar_capabilities_str
        )

        definer_agent = await context_service.cognitive_service.aget_client_for_role(
            "CodeReviewer"
        )
        raw_response = await definer_agent.make_request_async(
            final_prompt, user_id="definer_agent"
        )

        match = re.search(r"([a-z0-9_]+\.[a-z0-9_.]+[a-z0-9_]+)", raw_response)
        if match:
            cleaned_key = match.group(1).strip()
        else:
            cleaned_key = (
                raw_response.strip().replace("`", "").replace("'", "").replace('"', "")
            )

        if cleaned_key in existing_keys:
            console.print(
                f"[yellow]Warning: AI suggested existing key '{cleaned_key}' for a new symbol. Skipping to avoid conflict.[/yellow]"
            )
            return {"id": symbol["id"], "key": "error.duplicate_key"}

        return {"id": symbol["id"], "key": cleaned_key}

    except Exception as e:
        logger.warning(
            f"Context building or AI call failed during definition for {symbol['symbol_path']}: {e}"
        )
        return {"id": symbol["id"], "key": "error.processing_failed"}


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


async def _define_new_symbols(context_service: ContextService):
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

    worker_fn = partial(
        define_single_symbol,
        context_service=context_service,
        existing_keys=existing_keys,
    )

    processor = ThrottledParallelProcessor(description="Defining symbols...")
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
