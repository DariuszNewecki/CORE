# src/features/self_healing/prune_private_capabilities.py
# ID: a89bad59-de22-43f7-b70c-60446902e923

"""
A self-healing tool that scans the codebase and removes # CAPABILITY tags
from private symbols (those starting with an underscore).

Enforces the 'caps.ignore_private' constitutional policy via governed actions.
Refactored to use the canonical ActionExecutor Gateway for all mutations.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from body.atomic.executor import ActionExecutor

# REFACTORED: Removed direct settings import
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: bb384d72-6190-400b-9479-20f53e2e63da
async def prune_private_capability_tags(
    context: CoreContext, write: bool = False
) -> int:
    """
    Finds and removes capability tags from private symbols (_ or __) via the Action Gateway.

    Args:
        context: CoreContext (Required for ActionExecutor and KnowledgeService)
        write: If True, apply changes; if False, perform dry-run.

    Returns:
        The total number of tags removed or proposed for removal.
    """
    logger.info("🐍 Scanning for misplaced capability tags on private symbols...")

    executor = ActionExecutor(context)
    knowledge_service = context.knowledge_service

    # Use the DB-backed knowledge graph (SSOT)
    graph = await knowledge_service.get_graph()
    symbols = graph.get("symbols", {})

    # Identify private symbols that shouldn't have tags
    private_symbols_with_tags = [
        s
        for s in symbols.values()
        if s.get("name", "").startswith("_")
        and s.get("capability") != "unassigned"
        and s.get("capability") is not None
    ]

    if not private_symbols_with_tags:
        logger.info("✅ Compliance perfect: No private symbols have capability tags.")
        return 0

    logger.info(
        "Found %d private symbol(s) with illegal capability tags.",
        len(private_symbols_with_tags),
    )

    # Group violations by file to minimize gateway transactions
    files_to_modify: dict[Path, list[int]] = {}
    tag_pattern = re.compile(r"^\s*#\s*CAPABILITY:\s*\S+\s*$", re.IGNORECASE)

    for symbol in private_symbols_with_tags:
        file_path_str = symbol.get("file") or symbol.get("file_path")
        if not file_path_str:
            continue

        file_path = context.git_service.repo_path / file_path_str
        line_num = symbol.get("line_number", 0)

        if file_path not in files_to_modify:
            if file_path.exists():
                files_to_modify[file_path] = []
            else:
                logger.warning(
                    "File not found for symbol %s: %s",
                    symbol.get("symbol_path"),
                    file_path,
                )
                continue

        files_to_modify[file_path].append(line_num)

    total_pruned = 0
    write_mode = write

    # Execute mutations via Gateway
    for file_path, line_nums in files_to_modify.items():
        try:
            rel_path = str(file_path.relative_to(context.git_service.repo_path))
            lines = file_path.read_text("utf-8").splitlines()

            modified = False
            # Sort lines descending to prevent index shifts
            for line_num in sorted(line_nums, reverse=True):
                # The tag is usually 1 or 2 lines above the symbol definition
                # We check the immediate vicinity
                lookback_range = range(max(0, line_num - 3), line_num)
                for idx in reversed(list(lookback_range)):
                    if idx < len(lines) and tag_pattern.match(lines[idx]):
                        logger.debug(
                            "   -> Found tag for removal in %s at line %d",
                            rel_path,
                            idx + 1,
                        )
                        lines.pop(idx)
                        modified = True
                        total_pruned += 1
                        break

            if modified:
                final_code = "\n".join(lines) + "\n"

                # CONSTITUTIONAL GATEWAY: Mutation is audited and guarded
                result = await executor.execute(
                    action_id="file.edit",
                    write=write_mode,
                    file_path=rel_path,
                    code=final_code,
                )

                if result.ok:
                    status = "Pruned" if write_mode else "Proposed"
                    logger.info("   -> [%s] %s", status, rel_path)
                else:
                    logger.error(
                        "   -> [BLOCKED] %s: %s", rel_path, result.data.get("error")
                    )

        except Exception as e:
            logger.error("Failed to process %s: %s", file_path.name, e)

    return total_pruned
