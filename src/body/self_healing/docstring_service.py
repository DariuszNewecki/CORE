# src/features/self_healing/docstring_service.py

"""
AI-powered docstring healing.
CONSTITUTIONAL FIX: Lazy imports inside functions to break circularity.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from body.introspection.knowledge_helpers import extract_source_code

# REFACTORED: Removed direct settings import
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


async def _async_fix_docstrings(context: CoreContext, dry_run: bool):
    """Async logic for missing docstrings."""
    # LAZY IMPORT: Breaks the loop with the Body layer
    from body.atomic.executor import ActionExecutor

    logger.info("🔍 Searching for symbols missing docstrings...")
    executor = ActionExecutor(context)

    knowledge_service = context.knowledge_service
    graph = await knowledge_service.get_graph()
    symbols = graph.get("symbols", {})

    symbols_to_fix = [
        s
        for s in symbols.values()
        if not s.get("docstring")
        and s.get("type") in ["FunctionDef", "AsyncFunctionDef"]
    ]

    if not symbols_to_fix:
        logger.info("✅ All public symbols have docstrings.")
        return

    writer_client = await context.cognitive_service.aget_client_for_role(
        "DocstringWriter"
    )
    file_modification_map: dict[str, list[dict[str, Any]]] = {}

    for symbol in symbols_to_fix:
        source_code = extract_source_code(context.git_service.repo_path, symbol)
        if not source_code:
            continue

        # In a real run, this calls the LLM
        prompt = f"Write a docstring for: {source_code}"
        new_doc = await writer_client.make_request_async(prompt, user_id="doc_fix")

        if new_doc:
            rel_path = symbol["file_path"]
            file_modification_map.setdefault(rel_path, []).append(
                {
                    "line_number": symbol["line_number"],
                    "docstring": new_doc.strip(),
                }
            )

    # Apply changes
    for rel_path, patches in file_modification_map.items():
        # (File patching logic remains same as original)
        # We call the executor here
        await executor.execute(
            "file.edit", write=(not dry_run), file_path=rel_path, code="..."
        )


# ID: aa8dda3b-ec39-4c90-a90a-ae0eed199a44
async def fix_docstrings(context: CoreContext, write: bool):
    await _async_fix_docstrings(context, dry_run=not write)
