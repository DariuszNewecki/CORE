# src/will/governance/llm_resource_runner.py
"""
llm_resource authoring runner facade — Will-layer entry point for the
/llm-resources API (#821 Unit 3).

Synchronous, single-call wrapper over `author.llm_resource`, matching
cognitive_role_runner.py's shape: this validates/persists at most one row
and completes in milliseconds, so no core.sync_runs-style tracking table
is needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from shared.action_types import ActionResult
from shared.context import CoreContext


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ID: 2e6b0d4a-8c1f-4b5d-9e3a-7c1f5b9d3e7a
async def run_author_llm_resource(
    context: CoreContext, write: bool, definition: dict[str, Any]
) -> ActionResult:
    """Execute `author.llm_resource` via ActionExecutor.

    write=False validates the definition without persisting.
    write=True validates then creates-or-updates the row.
    """
    from body.atomic.executor import ActionExecutor

    executor = ActionExecutor(context)
    return await executor.execute(
        "author.llm_resource", write=write, definition=definition
    )


# ID: 5c9e3a7f-2d1b-4f6e-8a4c-7b3d9f1e5a2c
async def run_setup_llm(
    context: CoreContext,
    write: bool,
    api_url: str,
    embedding_model: str,
    chat_model: str,
    locality: str,
    embedding_api_url: str = "",
    embedding_locality: str = "",
) -> ActionResult:
    """Execute `setup.llm` via ActionExecutor (#1374)."""
    from body.atomic.executor import ActionExecutor

    executor = ActionExecutor(context)
    return await executor.execute(
        "setup.llm",
        write=write,
        api_url=api_url,
        embedding_model=embedding_model,
        chat_model=chat_model,
        locality=locality,
        embedding_api_url=embedding_api_url,
        embedding_locality=embedding_locality,
    )


# ID: 9a4d7e2b-6f3c-4b8a-9d1e-3c7f5a2b8e6d
async def run_check_llm(context: CoreContext, session: AsyncSession) -> dict[str, Any]:
    """Call the embedding model and the chat model once each (#1374).

    Reloads the shared CognitiveService first: it loaded its model list at
    start-up, before `setup.llm` wrote the rows. Writes nothing. Each part
    reports ok and, when it fails, the error a newcomer can act on. The chat
    call goes through the `llm_setup_check` PromptModel, whose manifest names
    the role; the expected vector size is the vector store's own.
    """
    from shared.models.prompt_model import PromptModel

    service = context.cognitive_service
    if service is None:
        return {"ok": False, "error": "the API has no cognitive service"}
    await service.reload(session)

    result: dict[str, Any] = {}
    qdrant = context.qdrant_service
    expected_dim = int(qdrant.vector_size) if qdrant is not None else None
    try:
        vector = await service.get_embedding_for_code("def hello(): return 1")
        dim = len(vector or [])
        embedding: dict[str, Any] = {
            "ok": dim > 0 and (expected_dim is None or dim == expected_dim),
            "dimensions": dim,
            "expected_dimensions": expected_dim,
        }
        if not embedding["ok"]:
            embedding["error"] = (
                f"the embedding model returns {dim} dimensions; CORE's vector "
                f"collections use {expected_dim}"
            )
        result["embedding"] = embedding
    except Exception as exc:
        result["embedding"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    try:
        model = PromptModel.load("llm_setup_check")
        client = await service.aget_client_for_role(model.manifest.role)
        reply = await model.invoke(client, {})
        result["chat"] = {"ok": bool((reply or "").strip()), "reply": reply[:80]}
    except Exception as exc:
        result["chat"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    result["ok"] = all(part.get("ok") for part in result.values())
    return result
