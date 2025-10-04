# src/features/self_healing/enrichment_service.py
from __future__ import annotations

import asyncio
from functools import partial
from typing import Any, Dict, List

from core.cognitive_service import CognitiveService
from rich.console import Console
from services.clients.qdrant_client import QdrantService
from services.database.session_manager import get_session
from shared.config import settings
from shared.logger import getLogger
from shared.utils.parallel_processor import ThrottledParallelProcessor
from shared.utils.parsing import extract_json_from_response
from sqlalchemy import text

from features.introspection.knowledge_helpers import extract_source_code

console = Console()
log = getLogger("enrichment_service")
REPO_ROOT = settings.REPO_PATH


async def _get_symbols_to_enrich() -> List[Dict[str, Any]]:
    """Fetches symbols that are ready for enrichment (have a null or placeholder description)."""
    async with get_session() as session:
        # --- FIX #1: Query the correct table (core.symbols) and look for NULL/TBD intents ---
        result = await session.execute(
            text(
                """
                SELECT uuid, symbol_path, module AS file_path, vector_id
                FROM core.symbols
                WHERE intent IS NULL OR intent = 'TBD'
            """
            )
        )
        return [dict(row._mapping) for row in result]


async def _enrich_single_symbol(
    symbol: Dict[str, Any],
    cognitive_service: CognitiveService,
    qdrant_service: QdrantService,
) -> Dict[str, str]:
    """Uses an AI to generate a description for a single symbol."""
    try:
        log.debug(f"Enriching symbol: {symbol.get('symbol_path')}")
        source_code = extract_source_code(REPO_ROOT, symbol)
        if not source_code:
            return {"uuid": symbol["uuid"], "description": "error.code_not_found"}

        prompt_template = (
            REPO_ROOT / ".intent/mind/prompts/enrich_symbol.prompt"
        ).read_text("utf-8")
        final_prompt = prompt_template.format(
            symbol_path=symbol["symbol_path"],
            file_path=symbol["file_path"],
            similar_capabilities="Context from similar capabilities is disabled for this operation.",
            source_code=source_code,
        )

        log.debug(
            f"FINAL PROMPT for {symbol['symbol_path']}:\n---\n{final_prompt}\n---"
        )

        # --- FIX #2: Use the 'Coder' role, which is assigned to the code-aware model ---
        enricher_agent = await cognitive_service.aget_client_for_role("Coder")

        raw_response = await enricher_agent.make_request_async(
            final_prompt, user_id="enricher_agent"
        )

        parsed_response = extract_json_from_response(raw_response)
        if parsed_response and isinstance(parsed_response, dict):
            description = parsed_response.get(
                "description", "error.parsing_failed"
            ).strip()
        else:
            description = "error.parsing_failed"

        try:
            delay_str = settings.model_extra.get("LLM_SECONDS_BETWEEN_REQUESTS", "1")
            delay = int(delay_str)
        except (ValueError, TypeError):
            delay = 1
        await asyncio.sleep(delay)

        return {"uuid": symbol["uuid"], "description": description}
    except Exception as e:
        log.error(f"Failed to enrich symbol '{symbol.get('symbol_path')}': {e}")
        return {"uuid": symbol["uuid"], "description": "error.processing_failed"}


async def _update_descriptions_in_db(descriptions: List[Dict[str, str]]):
    """Updates the 'intent' column for symbols in the database."""
    if not descriptions:
        return

    log.info(
        f"Attempting to update {len(descriptions)} descriptions in the database..."
    )
    async with get_session() as session:
        async with session.begin():
            await session.execute(
                text(
                    "UPDATE core.symbols SET intent = :description WHERE uuid = :uuid"
                ),
                descriptions,
            )
    log.info("Database update transaction completed.")


async def enrich_symbols(cognitive_service: CognitiveService, dry_run: bool):
    """The main orchestrator for the autonomous symbol enrichment process."""
    symbols_to_enrich = await _get_symbols_to_enrich()
    if not symbols_to_enrich:
        console.print(
            "[bold green]✅ No symbols with placeholder descriptions found.[/bold green]"
        )
        return

    console.print(f"   -> Found {len(symbols_to_enrich)} symbols to enrich...")

    qdrant_service = QdrantService()
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
        if d.get("description") and not d["description"].startswith("error.")
    ]

    if dry_run:
        console.print(
            "[bold yellow]-- DRY RUN: The following descriptions would be written --[/bold yellow]"
        )
        for d in valid_descriptions[:10]:
            console.print(
                f"  - Symbol UUID [dim]{d['uuid']}[/dim] -> '{d['description']}'"
            )
        if len(valid_descriptions) > 10:
            console.print(f"  - ... and {len(valid_descriptions) - 10} more.")
        return

    await _update_descriptions_in_db(valid_descriptions)
    console.print(
        f"   -> Successfully enriched {len(valid_descriptions)} symbols in the database."
    )
