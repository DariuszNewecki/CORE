# src/will/self_healing/docstring_service.py

"""
AI-powered docstring healing via constitutional PromptModel.

CONSTITUTIONAL ALIGNMENT:
- AI invocation routes through PromptModel.invoke() — never direct make_request_async().
- Mutations route through the governed ActionExecutor gateway.
- Ref: .intent/rules/ai/prompt_governance.json [ai.prompt.model_required]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from body.atomic.executor import ActionExecutor
from body.introspection.knowledge_helpers import extract_source_code
from shared.ai.prompt_model import PromptModel
from shared.config import settings
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


async def _async_fix_docstrings(
    context: CoreContext, dry_run: bool, limit: int = 0
) -> None:
    """
    Autonomously recover missing docstrings for undocumented CORE symbols.

    Scans the knowledge graph for public functions and methods lacking
    documentation, generates constitutionally-grounded docstrings via the
    DocstringWriter PromptModel, and applies them through the governed
    ActionExecutor.

    Args:
        context: CoreContext providing cognitive, knowledge, and executor services.
        dry_run: When True, reports what would change without writing to filesystem.
    """
    logger.info("Searching for symbols missing docstrings...")

    executor = ActionExecutor(context)
    knowledge_service = context.knowledge_service
    graph = await knowledge_service.get_graph()
    symbols = graph.get("symbols", {})

    symbols_to_fix = [
        s
        for s in symbols.values()
        if not s.get("docstring") and s.get("kind") == "function"
    ]

    if limit > 0:
        symbols_to_fix = symbols_to_fix[:limit]

    if not symbols_to_fix:
        logger.info("All public symbols have docstrings.")
        return

    logger.info("Found %d symbol(s) requiring docstrings.", len(symbols_to_fix))

    # Load PromptModel — validates artifact completeness at load time
    # Raises FileNotFoundError if var/prompts/docstring_writer/ is incomplete
    prompt_model = PromptModel.load("docstring_writer")

    writer_client = await context.cognitive_service.aget_client_for_role("Coder")

    file_modification_map: dict[str, list[dict[str, Any]]] = {}

    for i, symbol in enumerate(symbols_to_fix, 1):
        if i % 10 == 0:
            logger.debug("Docstring progress: %d/%d", i, len(symbols_to_fix))

        try:
            source_code = extract_source_code(settings.REPO_PATH, symbol)
            if not source_code:
                continue

            # Constitutional invocation — PromptModel handles system prompt,
            # input validation, and output contract enforcement
            new_doc = await prompt_model.invoke(
                context={"source_code": source_code},
                client=writer_client,
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

        except ValueError as e:
            # Output contract violation — log and skip, don't crash the whole run
            logger.warning(
                "PromptModel output validation failed for '%s': %s",
                symbol.get("symbol_path", "?"),
                e,
            )
        except Exception as e:
            logger.error("Could not process %s: %s", symbol.get("symbol_path"), e)

    if not file_modification_map:
        logger.info("No docstrings generated.")
        return

    total = sum(len(v) for v in file_modification_map.values())
    logger.info(
        "Generated %d docstring(s) across %d file(s).",
        total,
        len(file_modification_map),
    )

    if dry_run:
        logger.info("[DRY RUN] Would write %d docstrings — skipping.", total)
        return

    # Mutations via governed ActionExecutor gateway
    for rel_path, modifications in file_modification_map.items():
        for mod in modifications:
            await executor.execute(
                "write.docstring",
                file_path=rel_path,
                line_number=mod["line_number"],
                docstring=mod["docstring"],
                symbol_name=mod["symbol_name"],
            )


# ID: f74db998-8680-40b8-bd62-e6495b5d6df3
async def fix_docstrings(
    context: CoreContext, write: bool = False, limit: int = 0
) -> None:
    """
    Public entry point for the fix docstrings self-healing command.

    Args:
        context: CoreContext with all required services.
        write: When True, persists changes. When False, dry-run only.
        limit: Max symbols to process. 0 means no limit.
    """
    await _async_fix_docstrings(context=context, dry_run=not write, limit=limit)
