# src/features/project_lifecycle/definition_service.py
from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from rich.console import Console
from sqlalchemy import text

from core.cognitive_service import CognitiveService
from features.introspection.knowledge_helpers import extract_source_code
from services.repositories.db.engine import get_session
from shared.config import settings

console = Console()


# ID: 4fe1a3d1-a3a9-428b-9e6a-7282fe7ffe36
async def get_undefined_symbols() -> List[Dict[str, Any]]:
    """Fetches symbols from the DB that have a UUID but no capability key yet."""
    async with get_session() as session:
        # --- THIS IS THE FIX ---
        # Query the knowledge_graph VIEW, which has all the necessary columns,
        # including the line numbers that extract_source_code needs.
        result = await session.execute(
            text(
                "SELECT uuid, file, symbol_path, line_number, end_line_number FROM core.knowledge_graph WHERE capability IS NULL"
            )
        )
        return [dict(row._mapping) for row in result]


# ID: c5e8625f-56fb-414c-b5b6-652c35061ce5
async def define_single_symbol(
    symbol: Dict[str, Any], cognitive_service: CognitiveService
) -> Dict[str, str]:
    """Uses an AI to generate a definition for a single symbol."""
    try:
        source_code = extract_source_code(settings.REPO_PATH, symbol)
    except (ValueError, FileNotFoundError) as e:
        console.print(
            f"[yellow]Warning: Could not extract source for {symbol.get('symbol_path', 'unknown symbol')}: {e}[/yellow]"
        )
        return {"uuid": symbol["uuid"], "key": "error.code_not_found"}

    if not source_code:
        return {"uuid": symbol["uuid"], "key": "error.code_not_found"}

    prompt_template = "Analyze the following code and propose a structured, dot-notation capability key (e.g., domain.subdomain.action):\n\n```python\n{code}\n```\n\nRespond with ONLY the key."
    final_prompt = prompt_template.format(code=source_code)

    definer_agent = cognitive_service.get_client_for_role("Planner")
    suggested_key = await definer_agent.make_request_async(
        final_prompt, user_id="definer_agent"
    )

    return {"uuid": symbol["uuid"], "key": suggested_key.strip()}


# ID: d1d22715-6f9f-4742-9a8e-9fdeef776af6
async def update_definitions_in_db(definitions: List[Dict[str, str]]):
    """Updates the 'key' column for symbols in the database."""
    # Filter out any symbols that failed during the definition process
    valid_definitions = [
        d for d in definitions if d.get("key") and not d["key"].startswith("error.")
    ]
    if not valid_definitions:
        return

    async with get_session() as session:
        async with session.begin():
            await session.execute(
                text("UPDATE core.symbols SET key = :key WHERE uuid = :uuid"),
                valid_definitions,
            )


# ID: 0d859072-4aa5-49b6-9cf5-cd26405892f6
async def define_new_symbols():
    """The main orchestrator for the autonomous definition process."""
    undefined_symbols = await get_undefined_symbols()
    if not undefined_symbols:
        console.print("   -> No new symbols to define.")
        return

    console.print(f"   -> Found {len(undefined_symbols)} new symbols to define...")
    cognitive_service = CognitiveService(settings.REPO_PATH)

    tasks = [
        define_single_symbol(symbol, cognitive_service) for symbol in undefined_symbols
    ]
    definitions = await asyncio.gather(*tasks)

    await update_definitions_in_db(definitions)

    valid_definitions_count = len(
        [d for d in definitions if d.get("key") and not d["key"].startswith("error.")]
    )
    console.print(
        f"   -> Successfully defined {valid_definitions_count} new capabilities."
    )
