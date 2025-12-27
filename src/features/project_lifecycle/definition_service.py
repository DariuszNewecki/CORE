# src/features/project_lifecycle/definition_service.py

"""
Symbol definition service - assigns capability keys to public symbols.

CONSTITUTIONAL FIX: Uses SymbolDefinitionRepository with proper transaction boundaries.
Transaction management at controller level, not service level.
"""

from __future__ import annotations

import re
import time
from functools import partial
from pathlib import Path
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
    Get symbols needing definition, filtering out stale ones.

    CONSTITUTIONAL: Uses Repository and manages transaction boundary.

    Args:
        session: Database session (injected dependency)
        limit: Maximum number of symbols to retrieve
    """
    repo = SymbolDefinitionRepository(session)

    # Get symbols from repository
    symbols = await repo.get_undefined_symbols(limit)

    # Validate file existence
    valid_symbols = []
    stale_ids = []

    for symbol in symbols:
        # Check if the module file still exists
        module_path = symbol.get("file_path") or symbol.get("module", "")
        if module_path:
            file_path = Path(module_path)
            if file_path.exists():
                valid_symbols.append(symbol)
            else:
                stale_ids.append(symbol["id"])
                logger.debug(
                    "Skipping stale symbol '%s' - file not found: %s",
                    symbol.get("symbol_path"),
                    file_path,
                )
        else:
            # No file path means we can't validate - include it
            valid_symbols.append(symbol)

    # Mark stale symbols as broken
    if stale_ids:
        await repo.mark_stale_symbols_broken(stale_ids)
        await session.commit()  # Transaction boundary here
        logger.info(
            "Marked %d stale symbols as 'broken' (files not found)", len(stale_ids)
        )

    logger.info(
        "Found %d symbols needing definition (limit=%d, filtered=%d stale)",
        len(valid_symbols),
        limit,
        len(stale_ids),
    )
    return valid_symbols


def _extract_code(packet: dict[str, Any], file_path: str) -> str:
    for item in packet.get("context", []):
        if (
            item.get("item_type") == "code"
            and (item.get("path") or "").strip() == file_path
        ):
            return (item.get("content") or "").strip()

    for item in packet.get("context", []):
        if item.get("item_type") == "code":
            return (item.get("content") or "").strip()

    return ""


def _extract_similar_capabilities(packet: dict[str, Any], target_qualname: str) -> str:
    names: list[str] = []
    for item in packet.get("context", []):
        if item.get("item_type") != "symbol":
            continue
        name = (item.get("name") or "").strip()
        if not name or name == target_qualname:
            continue
        names.append(name)

    seen: set[str] = set()
    deduped: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            deduped.append(n)

    if not deduped:
        return "No similar capabilities found."

    deduped = deduped[:12]
    return "Found similar existing capabilities: " + ", ".join(
        f"`{n}`" for n in deduped
    )


def _make_processor(
    description: str, concurrency: int = 2
) -> ThrottledParallelProcessor:
    for kwargs in (
        {"concurrency_limit": concurrency},
        {"concurrency": concurrency},
        {"limit": concurrency},
    ):
        try:
            return ThrottledParallelProcessor(description=description, **kwargs)
        except TypeError:
            continue
    return ThrottledParallelProcessor(description=description)


async def _mark_attempt(
    symbol_id: Any,
    *,
    status: str,
    error: str | None = None,
    key: str | None = None,
    session: AsyncSession,
) -> None:
    """
    Mark a symbol definition attempt.

    CONSTITUTIONAL FIX: Uses Repository, no commit (caller manages transaction).

    Args:
        symbol_id: Symbol ID to update
        status: New status
        error: Optional error message
        key: Optional capability key
        session: Database session (caller manages transaction boundary)
    """
    repo = SymbolDefinitionRepository(session)
    await repo.mark_attempt(symbol_id, status=status, error=error, key=key)

    # NO COMMIT - caller manages transaction


# ID: 912ae5b0-f073-4a3a-9df1-a53cff7da99a
async def define_single_symbol(
    symbol: dict[str, Any],
    context_service: ContextService,
    session_factory: Any,  # Callable that returns async context manager
) -> dict[str, Any]:
    """
    Use an LLM to generate a capability key for a single symbol.

    CONSTITUTIONAL: Manages transaction boundary at this level.

    Args:
        symbol: Symbol dictionary with id, symbol_path, file_path, qualname
        context_service: Service for building context
        session_factory: Factory function to create database sessions
    """
    symbol_id = symbol["id"]
    symbol_path = symbol["symbol_path"]
    file_path = symbol["file_path"]
    target_qualname = symbol["qualname"]

    task_spec = {
        "task_id": f"define-{symbol_id}",
        "task_type": "refactor",
        "summary": f"Define capability for {symbol_path}",
        "target_file": file_path,
        "target_symbol": target_qualname,
        "scope": {"traversal_depth": 1},
    }

    async def _attempt(prompt: str) -> str | None:
        agent = await context_service.cognitive_service.aget_client_for_role(
            "CodeReviewer"
        )
        response = await agent.make_request_async(prompt, user_id="symbol-definer")

        try:
            parsed = extract_json_from_response(response)
            if isinstance(parsed, dict):
                raw = parsed.get("suggested_capability")
                if isinstance(raw, str):
                    return raw.strip()
        except Exception:
            pass

        match = re.search(r"[a-z0-9_]+\.[a-z0-9_.]+", response)
        return match.group(0).strip() if match else None

    try:
        packet = await context_service.build_for_task(task_spec, use_cache=True)
        source_code = _extract_code(packet, file_path)

        if not source_code:
            # Mark as invalid - commit this error state
            async with session_factory() as session:
                await _mark_attempt(
                    symbol_id,
                    status="invalid",
                    error="context.code_missing",
                    session=session,
                )
                await session.commit()  # Transaction boundary here

            logger.warning("❌ No code extracted for %s", symbol_path)
            return {"id": symbol_id, "key": None}

        similar_capabilities = _extract_similar_capabilities(packet, target_qualname)

        template = settings.paths.prompt("capability_definer").read_text(
            encoding="utf-8"
        )
        prompt = template.format(
            code=source_code, similar_capabilities=similar_capabilities
        )

        key = await _attempt(prompt)

        if not key or "." not in key or " " in key:
            # Mark as invalid - commit this error state
            async with session_factory() as session:
                await _mark_attempt(
                    symbol_id,
                    status="invalid",
                    error="llm.invalid_format",
                    session=session,
                )
                await session.commit()  # Transaction boundary here

            return {"id": symbol_id, "key": None}

        # SUCCESS - commit defined state
        async with session_factory() as session:
            await _mark_attempt(symbol_id, status="defined", key=key, session=session)
            await session.commit()  # Transaction boundary here

        return {"id": symbol_id, "key": key}

    except Exception as exc:
        # EXCEPTION - commit error state
        try:
            async with session_factory() as session:
                await _mark_attempt(
                    symbol_id,
                    status="invalid",
                    error=f"exception:{exc}",
                    session=session,
                )
                await session.commit()  # Transaction boundary here
        except Exception as commit_exc:
            logger.error("Failed to mark exception for %s: %s", symbol_id, commit_exc)

        logger.exception("❌ Definition failed for %s", symbol_path)
        return {"id": symbol_id, "key": None}


@atomic_action(
    action_id="manage.define-symbols",
    intent="Define capabilities for public symbols",
    impact=ActionImpact.WRITE_DATA,
    policies=["symbol_identification"],
    category="management",
)
# ID: 45e0e360-c263-430b-923d-0c804d90df17
async def define_symbols(
    context_service: ContextService,
    session_factory: Any,  # Callable that returns async context manager
) -> ActionResult:
    """
    Define capabilities for undefined symbols.

    Args:
        context_service: Service for building context
        session_factory: Factory function to create database sessions
    """
    start = time.time()

    async with session_factory() as session:
        symbols = await get_undefined_symbols(session, limit=500)

    if not symbols:
        return ActionResult(
            action_id="manage.define-symbols",
            ok=True,
            data={"attempted": 0, "defined": 0},
            duration_sec=0,
            impact=ActionImpact.READ_ONLY,
        )

    processor = _make_processor(description="Defining symbols", concurrency=2)

    results = await processor.run_async(
        symbols,
        partial(
            define_single_symbol,
            context_service=context_service,
            session_factory=session_factory,
        ),
    )

    duration = time.time() - start

    return ActionResult(
        action_id="manage.define-symbols",
        ok=True,
        data={
            "attempted": len(symbols),
            "defined": sum(1 for r in results if r.get("key")),
        },
        duration_sec=duration,
        impact=ActionImpact.WRITE_DATA,
    )


async def _define_new_symbols(
    context_service: ContextService,
    session_factory: Any,
) -> ActionResult:
    """Wrapper for define_symbols with injected dependencies."""
    return await define_symbols(context_service, session_factory)
