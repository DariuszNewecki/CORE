# src/features/project_lifecycle/definition_service.py

"""
Symbol definition service - assigns capability keys to public symbols.

CONSTITUTIONAL FIX:
- Separates LLM reasoning (Will) from persistence (Body).
- Uses SymbolDefinitionRepository for all database interactions.
- Manages discrete transaction boundaries for parallel processing efficiency.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from functools import partial
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.config import settings
from shared.infrastructure.context.service import ContextService
from shared.infrastructure.repositories.symbol_definition_repository import (
    SymbolDefinitionRepository,
)
from shared.logger import getLogger
from shared.utils.parallel_processor import ThrottledParallelProcessor
from shared.utils.parsing import extract_json_from_response


logger = getLogger(__name__)


# ID: b967b43c-3a4d-4b36-855f-12a434c0db4f
async def get_undefined_symbols(
    session: AsyncSession, limit: int = 500
) -> list[dict[str, Any]]:
    """
    Retrieves symbols requiring definition, filtering out stale entries.

    Args:
        session: Database session.
        limit: Max symbols to process.
    """
    repo = SymbolDefinitionRepository(session)
    symbols = await repo.get_undefined_symbols(limit)

    valid_symbols = []
    stale_ids = []

    for symbol in symbols:
        # Verify file still exists on disk before asking AI to reason about it
        module_path = symbol.get("file_path") or symbol.get("module", "")
        if module_path:
            file_path = settings.REPO_PATH / module_path
            if file_path.exists():
                valid_symbols.append(symbol)
            else:
                stale_ids.append(symbol["id"])
                logger.debug(
                    "Skipping stale symbol '%s' (file not found)",
                    symbol.get("symbol_path"),
                )
        else:
            valid_symbols.append(symbol)

    # Clean up stale references in the DB
    if stale_ids:
        await repo.mark_stale_symbols_broken(stale_ids)
        # Immediate commit for cleanup
        await session.commit()
        logger.info("Marked %d stale symbols as 'broken'.", len(stale_ids))

    return valid_symbols


def _extract_code(packet: dict[str, Any], file_path: str) -> str:
    """Extracts relevant code from a ContextPackage."""
    for item in packet.get("context", []):
        if (
            item.get("item_type") == "code"
            and (item.get("path") or "").strip() == file_path
        ):
            return (item.get("content") or "").strip()

    # Fallback to any code in the packet
    for item in packet.get("context", []):
        if item.get("item_type") == "code":
            return (item.get("content") or "").strip()
    return ""


def _extract_similar_capabilities(packet: dict[str, Any], target_qualname: str) -> str:
    """Extracts existing similar capability keys to provide few-shot context."""
    names = [
        (item.get("name") or "").strip()
        for item in packet.get("context", [])
        if item.get("item_type") == "symbol" and item.get("name") != target_qualname
    ]

    deduped = sorted(list(set(filter(None, names))))[:12]
    if not deduped:
        return "No similar capabilities found."
    return "Existing capabilities for reference: " + ", ".join(
        f"`{n}`" for n in deduped
    )


async def _mark_attempt(
    symbol_id: Any,
    *,
    status: str,
    session: AsyncSession,
    error: str | None = None,
    key: str | None = None,
) -> None:
    """Body: Persists a definition attempt via the Repository."""
    repo = SymbolDefinitionRepository(session)
    await repo.mark_attempt(symbol_id, status=status, error=error, key=key)
    # We commit immediately within the worker to ensure work is saved during parallel batches
    await session.commit()


# ID: 912ae5b0-f073-4a3a-9df1-a53cff7da99a
async def define_single_symbol(
    symbol: dict[str, Any],
    context_service: ContextService,
    session_factory: Callable[[], Any],
) -> dict[str, Any]:
    """
    Will: Orchestrates the AI reasoning for a single symbol.
    Each call uses its own session to enable independent commits in parallel.
    """
    symbol_id = symbol["id"]
    symbol_path = symbol["symbol_path"]
    file_path = symbol["file_path"]
    target_qualname = symbol["qualname"]

    task_spec = {
        "task_id": f"define-{symbol_id}",
        "task_type": "metadata.refine",
        "summary": f"Define capability for {symbol_path}",
        "target_file": file_path,
        "target_symbol": target_qualname,
        "scope": {"traversal_depth": 1},
    }

    try:
        # 1. Build semantic context
        packet = await context_service.build_for_task(task_spec, use_cache=True)
        source_code = _extract_code(packet, file_path)

        if not source_code:
            async with session_factory() as session:
                await _mark_attempt(
                    symbol_id,
                    status="invalid",
                    error="context.code_missing",
                    session=session,
                )
            return {"id": symbol_id, "key": None}

        # 2. Invoke AI Reasoning (Will)
        similar_context = _extract_similar_capabilities(packet, target_qualname)

        # Resolve prompt via PathResolver
        template_path = settings.paths.prompt("capability_definer")
        prompt = template_path.read_text(encoding="utf-8").format(
            code=source_code, similar_capabilities=similar_context
        )

        agent = await context_service.cognitive_service.aget_client_for_role(
            "CodeReviewer"
        )
        response = await agent.make_request_async(prompt, user_id="symbol-definer")

        # 3. Parse result
        key = None
        try:
            parsed = extract_json_from_response(response)
            if isinstance(parsed, dict) and "suggested_capability" in parsed:
                key = str(parsed["suggested_capability"]).strip()
        except Exception:
            # Regex fallback
            match = re.search(r"[a-z0-9_]+\.[a-z0-9_.]+", response)
            key = match.group(0).strip() if match else None

        if not key or "." not in key:
            async with session_factory() as session:
                await _mark_attempt(
                    symbol_id,
                    status="invalid",
                    error="llm.invalid_format",
                    session=session,
                )
            return {"id": symbol_id, "key": None}

        # 4. Persist success (Body)
        async with session_factory() as session:
            await _mark_attempt(symbol_id, status="defined", key=key, session=session)

        logger.info("✅ Defined: %s -> %s", target_qualname, key)
        return {"id": symbol_id, "key": key}

    except Exception as exc:
        logger.error("❌ Failed to define %s: %s", symbol_path, exc)
        async with session_factory() as session:
            await _mark_attempt(
                symbol_id,
                status="invalid",
                error=f"exception:{type(exc).__name__}",
                session=session,
            )
        return {"id": symbol_id, "key": None}


@atomic_action(
    action_id="manage.define-symbols",
    intent="Assign capability keys to public symbols via AI reasoning",
    impact=ActionImpact.WRITE_DATA,
    policies=["symbol_identification"],
    category="management",
)
# ID: 45e0e360-c263-430b-923d-0c804d90df17
async def define_symbols(
    context_service: ContextService,
    session_factory: Callable[[], Any],
) -> ActionResult:
    """
    Main entry point for batch symbol definition.
    """
    start_time = time.time()

    # 1. Gather tasks
    async with session_factory() as session:
        symbols = await get_undefined_symbols(session, limit=100)

    if not symbols:
        return ActionResult(
            action_id="manage.define-symbols",
            ok=True,
            data={"attempted": 0, "defined": 0},
            duration_sec=time.time() - start_time,
            impact=ActionImpact.READ_ONLY,
        )

    # 2. Execute parallel reasoning
    # Throttled to respect API rate limits defined in settings
    processor = ThrottledParallelProcessor(description="Defining symbols")

    results = await processor.run_async(
        symbols,
        partial(
            define_single_symbol,
            context_service=context_service,
            session_factory=session_factory,
        ),
    )

    defined_count = sum(1 for r in results if r.get("key"))

    return ActionResult(
        action_id="manage.define-symbols",
        ok=True,
        data={
            "attempted": len(symbols),
            "defined": defined_count,
            "failed": len(symbols) - defined_count,
        },
        duration_sec=time.time() - start_time,
        impact=ActionImpact.WRITE_DATA,
    )
