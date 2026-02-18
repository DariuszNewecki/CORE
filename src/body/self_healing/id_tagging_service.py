# src/features/self_healing/id_tagging_service.py
# ID: 7babae48-7877-48fb-b653-042c97161139

"""
Provides a service to find and assign missing constitutional ID anchors to public symbols.
Refactored to use the canonical ActionExecutor Gateway for all mutations.
"""

from __future__ import annotations

import ast
import uuid
from collections import defaultdict
from typing import TYPE_CHECKING

from body.atomic.executor import ActionExecutor
from shared.ast_utility import find_symbol_id_and_def_line

# REFACTORED: Removed direct settings import
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


def _is_public(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> bool:
    """Determines if a symbol is public (not starting with _ or a dunder)."""
    is_dunder = node.name.startswith("__") and node.name.endswith("__")
    return not node.name.startswith("_") and (not is_dunder)


# ID: 17328e3a-5e37-48ff-94d4-c3f4697825d5
async def assign_missing_ids(context: CoreContext, write: bool = False) -> int:
    """
    Scans all Python files in the 'src/' directory, finds public symbols
    missing an '# ID:' tag, and adds a new UUID tag via the ActionExecutor.

    Args:
        context: CoreContext (Required for ActionExecutor)
        write: If True, apply changes; if False, perform dry-run.

    Returns:
        The total number of IDs assigned or proposed.
    """
    logger.info("🔍 Scanning for missing Constitutional IDs...")

    executor = ActionExecutor(context)
    src_dir = context.git_service.repo_path / "src"
    total_ids_assigned = 0
    files_to_fix = defaultdict(list)

    if not src_dir.exists():
        logger.warning("Source directory not found: %s", src_dir)
        return 0

    # 1. Discovery Phase (AST Scan)
    for file_path in src_dir.rglob("*.py"):
        try:
            content = file_path.read_text("utf-8")
            source_lines = content.splitlines()
            tree = ast.parse(content, filename=str(file_path))

            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    if not _is_public(node):
                        continue

                    id_result = find_symbol_id_and_def_line(node, source_lines)
                    if not id_result.has_id:
                        files_to_fix[file_path].append(
                            {
                                "line_number": id_result.definition_line_num,
                                "name": node.name,
                            }
                        )
        except Exception as e:
            logger.error("Error analyzing %s: %s", file_path.name, e)

    if not files_to_fix:
        logger.info("✅ All public symbols have constitutional IDs.")
        return 0

    # 2. Execution Phase (Gateway dispatch)
    for file_path, fixes in files_to_fix.items():
        # Sort by line number descending to prevent line-shift errors during insertion
        fixes.sort(key=lambda x: x["line_number"], reverse=True)

        try:
            rel_path = str(file_path.relative_to(context.git_service.repo_path))
            lines = file_path.read_text("utf-8").splitlines()

            for fix in fixes:
                line_index = fix["line_number"] - 1
                original_line = lines[line_index]
                indentation = len(original_line) - len(original_line.lstrip(" "))
                new_id = str(uuid.uuid4())
                tag_line = f"{' ' * indentation}# ID: {new_id}"
                lines.insert(line_index, tag_line)
                total_ids_assigned += 1

            final_code = "\n".join(lines) + "\n"

            # CONSTITUTIONAL GATEWAY: Metadata-only mutation with semantic proof
            result = await executor.execute(
                action_id="file.tag_metadata",
                write=write,
                file_path=rel_path,
                code=final_code,
                allowed_operations=["comment.insert"],
            )

            if result.ok:
                mode_str = "Fixed" if write else "Proposed"
                logger.info("   -> [%s] %d IDs in %s", mode_str, len(fixes), rel_path)
            else:
                # IMPROVED: Show full constitutional violation context
                error_msg = result.data.get("error") or "unknown error"
                violations = result.data.get("violations", [])

                logger.error(
                    "   -> [BLOCKED] %s: %s",
                    rel_path,
                    error_msg,
                )

                # Log violation details in debug mode
                for violation in violations[:3]:
                    logger.debug("        - %s", violation)

        except Exception as e:
            logger.error("Failed to prepare fix for %s: %s", file_path.name, e)

    logger.info("🏁 ID Assignment complete. Total: %d", total_ids_assigned)
    return total_ids_assigned
