# src/features/project_lifecycle/definition_service.py

"""Provides functionality for the definition_service module."""

from __future__ import annotations

import re
import time
from functools import partial
from typing import Any

from sqlalchemy import text

from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.config import settings
from shared.infrastructure.context.service import ContextService
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger
from shared.utils.parallel_processor import ThrottledParallelProcessor
from shared.utils.parsing import extract_json_from_response


logger = getLogger(__name__)


# ID: b967b43c-3a4d-4b36-855f-12a434c0db4f
async def get_undefined_symbols(limit: int = 500) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            text(
                """
                SELECT
                    id,
                    symbol_path,
                    file_path,
                    qualname,
                    definition_status,
                    attempt_count
                FROM core.symbols
                WHERE
                    is_public = TRUE
                    AND definition_status IN ('pending', 'invalid')
                    AND health_status != 'broken'
                    AND (
                        last_attempt_at IS NULL
                        OR last_attempt_at < NOW() - INTERVAL '1 hour'
                    )
                ORDER BY
                    attempt_count ASC,
                    last_attempt_at NULLS FIRST,
                    qualname
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        symbols = [dict(row._mapping) for row in result]
        logger.info(
            "Found %d symbols needing definition (limit=%d)", len(symbols), limit
        )
        return symbols


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
) -> None:
    async with get_session() as session:
        await session.execute(
            text(
                """
                UPDATE core.symbols
                SET
                    definition_status = :status,
                    definition_error = :error,
                    key = :key,
                    definition_source = 'llm',
                    defined_at = CASE WHEN :status = 'defined' THEN NOW() ELSE NULL END,
                    last_attempt_at = NOW(),
                    attempt_count = attempt_count + 1
                WHERE id = :id
                """
            ),
            {"id": symbol_id, "status": status, "error": error, "key": key},
        )
        await session.commit()


# ID: 912ae5b0-f073-4a3a-9df1-a53cff7da99a
async def define_single_symbol(
    symbol: dict[str, Any],
    context_service: ContextService,
) -> dict[str, Any]:
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
            await _mark_attempt(
                symbol_id, status="invalid", error="context.code_missing"
            )
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
            await _mark_attempt(symbol_id, status="invalid", error="llm.invalid_format")
            return {"id": symbol_id, "key": None}

        # IMPORTANT CHANGE:
        # key is NOT treated as unique. Multiple symbols may share one key.
        await _mark_attempt(symbol_id, status="defined", key=key)
        return {"id": symbol_id, "key": key}

    except Exception as exc:
        await _mark_attempt(symbol_id, status="invalid", error=f"exception:{exc}")
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
async def define_symbols(context_service: ContextService) -> ActionResult:
    start = time.time()

    symbols = await get_undefined_symbols(limit=500)
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
        partial(define_single_symbol, context_service=context_service),
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


async def _define_new_symbols(context_service: ContextService) -> ActionResult:
    return await define_symbols(context_service)
