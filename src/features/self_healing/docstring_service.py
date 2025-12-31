# src/features/self_healing/docstring_service.py
# ID: 43c3af5c-b9e3-4f5a-a95d-3b8945a71567

"""
AI-powered docstring healing.
Refactored to use the canonical ActionExecutor Gateway for all modifications.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from body.atomic.executor import ActionExecutor
from features.introspection.knowledge_helpers import extract_source_code
from shared.config import settings
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


async def _async_fix_docstrings(context: CoreContext, dry_run: bool):
    """
    Async core logic for finding and fixing missing docstrings.
    Mutations are routed through the governed ActionExecutor.
    """
    logger.info("🔍 Searching for symbols missing docstrings...")

    executor = ActionExecutor(context)
    knowledge_service = context.knowledge_service
    graph = await knowledge_service.get_graph()
    symbols = graph.get("symbols", {})

    # Filter for functions/methods missing docstrings
    symbols_to_fix = [
        s
        for s in symbols.values()
        if not s.get("docstring")
        and s.get("type") in ["FunctionDef", "AsyncFunctionDef"]
    ]

    if not symbols_to_fix:
        logger.info("✅ All public symbols have docstrings.")
        return

    logger.info("Found %d symbol(s) requiring docstrings.", len(symbols_to_fix))

    # Resolve Prompt via PathResolver (SSOT)
    prompt_path = settings.paths.prompt("fix_function_docstring")
    prompt_template = prompt_path.read_text(encoding="utf-8")

    writer_client = await context.cognitive_service.aget_client_for_role(
        "DocstringWriter"
    )

    # Group work by file to minimize gateway roundtrips
    file_modification_map: dict[str, list[dict[str, Any]]] = {}

    for i, symbol in enumerate(symbols_to_fix, 1):
        if i % 10 == 0:
            logger.debug("Docstring analysis progress: %d/%d", i, len(symbols_to_fix))

        try:
            source_code = extract_source_code(settings.REPO_PATH, symbol)
            if not source_code:
                continue

            # Will: Ask AI to generate the docstring
            new_doc = await writer_client.make_request_async(
                prompt_template.format(source_code=source_code),
                user_id="docstring_healing_service",
            )

            if new_doc:
                rel_path = symbol["file_path"]
                if rel_path not in file_modification_map:
                    file_modification_map[rel_path] = []

                file_modification_map[rel_path].append(
                    {
                        "line_number": symbol["line_number"],
                        "docstring": new_doc.strip(),
                        "symbol_name": symbol.get("name", "unknown"),
                    }
                )
        except Exception as e:
            logger.error("Could not process %s: %s", symbol.get("symbol_path"), e)

    # 2. Execution Phase (Gateway dispatch)
    write_mode = not dry_run
    for rel_path, patches in file_modification_map.items():
        try:
            full_path = settings.REPO_PATH / rel_path
            if not full_path.exists():
                continue

            lines = full_path.read_text(encoding="utf-8").splitlines()

            # Apply patches in reverse line order to maintain index integrity
            patches.sort(key=lambda x: x["line_number"], reverse=True)

            for patch in patches:
                line_idx = patch["line_number"] - 1  # 0-based
                if line_idx >= len(lines):
                    continue

                # Determine indentation of the target line
                original_line = lines[line_idx]
                indent = original_line[
                    : len(original_line) - len(original_line.lstrip())
                ]

                # Insert the docstring
                doc_block = f'{indent}    """{patch["docstring"]}"""'
                lines.insert(line_idx + 1, doc_block)

            final_code = "\n".join(lines) + "\n"

            # CONSTITUTIONAL GATEWAY: Mutation is audited and guarded
            result = await executor.execute(
                action_id="file.edit",
                write=write_mode,
                file_path=rel_path,
                code=final_code,
            )

            if result.ok:
                status = "Healed" if write_mode else "Proposed"
                logger.info(
                    "   -> [%s] %d docstrings in %s", status, len(patches), rel_path
                )
            else:
                logger.error(
                    "   -> [BLOCKED] %s: %s", rel_path, result.data.get("error")
                )

        except Exception as e:
            logger.error("Failed to prepare docstring fix for %s: %s", rel_path, e)


# ID: 43c3af5c-b9e3-4f5a-a95d-3b8945a71567
async def fix_docstrings(context: CoreContext, write: bool):
    """Uses an AI agent to find and add missing docstrings via governed actions."""
    await _async_fix_docstrings(context, dry_run=not write)
