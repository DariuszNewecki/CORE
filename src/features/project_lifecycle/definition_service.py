# src/features/project_lifecycle/definition_service.py
"""Services for defining capability keys for symbols (headless, no UI).

This module is part of the Body/Services layer and MUST remain headless:
- No Rich Console, no terminal UI.
- Only logging via the shared logger.
- Intended to be orchestrated by workflow/CLI layers (e.g. dev-sync),
  which own all terminal UI and reporting.
"""

from __future__ import annotations

import re
import time
from functools import partial
from typing import Any

from services.context import ContextService
from services.database.session_manager import get_session
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.config import settings
from shared.logger import getLogger
from shared.utils.parallel_processor import ThrottledParallelProcessor
from sqlalchemy import text

logger = getLogger(__name__)


# ID: 45733c48-d1d4-4e44-8e06-af55a656e585
async def get_undefined_symbols() -> list[dict[str, Any]]:
    """
    Fetch symbols that are ready for definition (public and have no key).

    Returns:
        A list of dicts with at least:
        - id
        - symbol_path
        - qualname
        - module
        - vector_id (may be None)
    """
    async with get_session() as session:
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
        return [dict(row._mapping) for row in result]


# ID: dd8e26e5-d606-42bf-89f2-36866461c0fe
async def define_single_symbol(
    symbol: dict[str, Any],
    context_service: ContextService,
    existing_keys: set[str],
) -> dict[str, Any]:
    """
    Use an LLM (via ContextService) to generate a capability key
    for a single symbol, using semantic context.

    Returns:
        {"id": <symbol_id>, "key": <capability_key or error_code>}
    """
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
        # Build context package (cached for speed)
        packet = await context_service.build_for_task(task_spec, use_cache=False)

        source_code = ""
        similar_capabilities_str = "No similar capabilities found."
        similar_keys: list[str] = []
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
            # Expected occasionally; keep noise low and rely on aggregate ActionResult.
            logger.debug(
                "No source code found in context for symbol '%s'",
                symbol.get("symbol_path"),
            )
            return {"id": symbol["id"], "key": "error.code_not_found"}

        if similar_keys:
            similar_capabilities_str = (
                "Found similar existing capabilities: "
                + ", ".join(f"`{k}`" for k in similar_keys)
            )

        # Load LLM prompt template
        prompt_template_path = settings.get_path("mind.prompts.capability_definer")
        prompt_template = prompt_template_path.read_text(encoding="utf-8")
        final_prompt = prompt_template.format(
            code=source_code,
            similar_capabilities=similar_capabilities_str,
        )

        # Call LLM via cognitive service
        definer_agent = await context_service.cognitive_service.aget_client_for_role(
            "CodeReviewer"
        )
        raw_response = await definer_agent.make_request_async(
            final_prompt,
            user_id="definer_agent",
        )

        # Extract key from response
        match = re.search(r"([a-z0-9_]+\.[a-z0-9_.]+[a-z0-9_]+)", raw_response)
        if match:
            cleaned_key = match.group(1).strip()
        else:
            cleaned_key = (
                raw_response.strip().replace("`", "").replace("'", "").replace('"', "")
            )

        # FIX: Allow existing keys. This enables multiple symbols to map to one capability.
        if cleaned_key in existing_keys:
            # This is valid reuse, not an error.
            pass

        return {"id": symbol["id"], "key": cleaned_key}

    except Exception as e:  # pragma: no cover - defensive logging
        logger.warning(
            "Definition failed for symbol '%s': %s",
            symbol.get("symbol_path"),
            e,
        )
        return {"id": symbol["id"], "key": "error.processing_failed"}


# ID: 3a986e52-f145-414c-9dee-dea773df5d8c
async def update_definitions_in_db(definitions: list[dict[str, Any]]) -> None:
    """
    Update the 'key' column for symbols in the database.

    Args:
        definitions: List of {"id": <symbol_id>, "key": <capability_key>}
    """
    if not definitions:
        return

    logger.info(
        "Persisting %d capability definitions to database...",
        len(definitions),
    )

    serializable_definitions = [
        {"id": str(d["id"]), "key": d["key"]} for d in definitions
    ]

    async with get_session() as session:
        async with session.begin():
            # Use executemany via SQLAlchemy for batch update
            await session.execute(
                text("UPDATE core.symbols SET key = :key WHERE id = :id"),
                serializable_definitions,
            )

    logger.info("Database definitions updated successfully.")


@atomic_action(
    action_id="manage.define-symbols",
    intent="Define capabilities for untagged public symbols",
    impact=ActionImpact.WRITE_DATA,
    policies=["symbol_identification", "data_governance"],
    category="management",
)
async def _define_new_symbols(context_service: ContextService) -> ActionResult:
    """
    Orchestrate the autonomous capability-definition process for undefined symbols.

    This function:
      - Finds symbols without a key.
      - Uses the ContextService + LLM to propose capability keys.
      - Persists valid definitions to the database.

    It is intentionally HEADLESS:
      - No Rich UI, no console printing.
      - Only structured logging via the shared logger.
      - Intended to be wrapped by higher-level workflows (e.g. dev-sync),
        which own terminal UI and progress reporting.

    Returns:
        ActionResult describing the outcome of the definition run.
    """
    start = time.time()

    try:
        undefined_symbols = await get_undefined_symbols()
        undefined_count = len(undefined_symbols)

        if not undefined_symbols:
            logger.info("No new symbols to define.")
            duration = time.time() - start
            return ActionResult(
                action_id="manage.define-symbols",
                ok=True,
                data={
                    "undefined_count": 0,
                    "attempted_definitions": 0,
                    "successful_definitions": 0,
                    "error_definitions": 0,
                },
                duration_sec=duration,
                impact=ActionImpact.READ_ONLY,
            )

        async with get_session() as session:
            result = await session.execute(
                text("SELECT key FROM core.symbols WHERE key IS NOT NULL")
            )
            existing_keys = {row[0] for row in result}

        logger.info("Found %d new symbols to define...", undefined_count)

        worker_fn = partial(
            define_single_symbol,
            context_service=context_service,
            existing_keys=existing_keys,
        )

        # Process in parallel (implementation may manage its own throttling/logging)
        processor = ThrottledParallelProcessor(description="Defining symbols...")
        definitions = await processor.run_async(undefined_symbols, worker_fn)

        # Filter out errors, but allow duplicates in the list (multiple symbols -> same key)
        valid_definitions = [
            d for d in definitions if d.get("key") and not d["key"].startswith("error.")
        ]

        error_count = len(definitions) - len(valid_definitions)

        await update_definitions_in_db(valid_definitions)

        logger.info(
            "Successfully defined %d new capabilities (errors: %d).",
            len(valid_definitions),
            error_count,
        )

        duration = time.time() - start
        impact = (
            ActionImpact.WRITE_DATA if valid_definitions else ActionImpact.READ_ONLY
        )

        return ActionResult(
            action_id="manage.define-symbols",
            ok=True,
            data={
                "undefined_count": undefined_count,
                "attempted_definitions": len(definitions),
                "successful_definitions": len(valid_definitions),
                "error_definitions": error_count,
            },
            duration_sec=duration,
            impact=impact,
        )

    except Exception as e:  # pragma: no cover - defensive safety net
        duration = time.time() - start
        logger.error("Error while defining new symbols: %s", e)
        return ActionResult(
            action_id="manage.define-symbols",
            ok=False,
            data={"error": str(e)},
            duration_sec=duration,
            impact=ActionImpact.READ_ONLY,
        )
