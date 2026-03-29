# src/body/self_healing/docstring_service.py

"""
AI-powered docstring healing via constitutional PromptModel.

CONSTITUTIONAL ALIGNMENT:
- AI invocation routes through PromptModel.invoke() — never direct make_request_async().
- Mutations route through the governed ActionExecutor gateway.
- Ref: .intent/rules/ai/prompt_governance.json [ai.prompt.model_required]
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING, Any

from body.atomic.executor import ActionExecutor
from shared.ai.prompt_model import PromptModel
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: f7d310e7-c416-4e65-a3c9-c56347297423
def extract_source_code(repo_root: Path, symbol_data: dict[str, Any]) -> str | None:
    """Extract source code for a symbol using its database record."""
    module_path = symbol_data.get("module")
    symbol_path_str = symbol_data.get("symbol_path")
    if not module_path or not symbol_path_str:
        return None
    file_path = repo_root / ("src/" + module_path.replace(".", "/") + ".py")
    if not file_path.exists():
        return None
    symbol_name = symbol_path_str.split("::")[-1]
    try:
        content = file_path.read_text("utf-8")
        tree = ast.parse(content, filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if getattr(node, "name", None) == symbol_name:
                    return ast.get_source_segment(content, node)
    except Exception:
        return None
    return None


def _has_docstring_in_source(repo_path: Path, symbol: dict[str, Any]) -> bool:
    """
    Check the live source file for an existing docstring.

    Reads the actual file on disk — never trusts the knowledge graph snapshot,
    which may be stale. Returns True if a docstring already exists so the
    caller can skip LLM generation entirely.
    """
    file_path_str = symbol.get("file_path", "")
    name = symbol.get("name", "")

    if not file_path_str or not name:
        return False

    file_path = repo_path / file_path_str
    if not file_path.exists():
        return False

    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception:
        return False

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == name and ast.get_docstring(node):
                return True

    return False


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
        limit: Max symbols to process. 0 means no limit.
    """
    logger.info("Searching for symbols missing docstrings...")

    executor = ActionExecutor(context)
    knowledge_service = context.knowledge_service
    graph = await knowledge_service.get_graph()
    symbols = graph.get("symbols", {})
    repo_path = Path(context.git_service.repo_path)

    # Guard: check live source file — never trust the stale knowledge graph.
    # This prevents repeated docstring injection when the graph hasn't resynced.
    symbols_to_fix = [
        s
        for s in symbols.values()
        if s.get("kind") == "function" and not _has_docstring_in_source(repo_path, s)
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

    writer_client = await context.cognitive_service.aget_client_for_role(
        prompt_model.manifest.role
    )

    file_modification_map: dict[str, list[dict[str, Any]]] = {}

    for i, symbol in enumerate(symbols_to_fix, 1):
        if i % 10 == 0:
            logger.debug("Docstring progress: %d/%d", i, len(symbols_to_fix))

        try:
            source_code = extract_source_code(repo_path, symbol)
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
