# src/body/self_healing/id_tagging_service.py

"""
Provides a service to find and assign missing constitutional ID anchors to public symbols.
Refactored to use the canonical ActionExecutor Gateway for all mutations.
"""

from __future__ import annotations

import ast
import re
import uuid
from collections import defaultdict
from typing import TYPE_CHECKING

from body.atomic.executor import ActionExecutor
from shared.ast_utility import find_symbol_id_and_def_line
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


def _is_public(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> bool:
    """Determines if a symbol is public (not starting with _ or a dunder)."""
    is_dunder = node.name.startswith("__") and node.name.endswith("__")
    return not node.name.startswith("_") and (not is_dunder)


def _is_id_tag(line: str) -> bool:
    """Returns True if the line is a # ID: <uuid> comment."""
    return bool(re.match(r"^\s*# ID:\s*[0-9a-fA-F\-]+\s*$", line))


def _strip_orphan_ids(content: str) -> tuple[str, int]:
    """
    Remove # ID: lines that are NOT immediately before a def/class line.
    These are file-level or orphaned IDs with no functional purpose.

    Returns (new_content, removed_count).
    """
    lines = content.splitlines(keepends=True)
    symbol_keywords = ("def ", "async def ", "class ")

    # Build set of line indices that are valid anchors (immediately before def/class)
    valid_anchor_indices: set[int] = set()
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if any(stripped.startswith(kw) for kw in symbol_keywords):
            if i > 0 and _is_id_tag(lines[i - 1]):
                valid_anchor_indices.add(i - 1)

    new_lines = []
    removed = 0
    for i, line in enumerate(lines):
        if _is_id_tag(line) and i not in valid_anchor_indices:
            removed += 1
            continue
        new_lines.append(line)

    return "".join(new_lines), removed


# ID: 17328e3a-5e37-48ff-94d4-c3f4697825d5
async def assign_missing_ids(context: CoreContext, write: bool = False) -> int:
    """
    Scans all Python files in src/, strips orphan file-level # ID: tags,
    then assigns missing # ID: anchors to public symbols via ActionExecutor.

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

    # 0. Cleanup Phase — strip orphan file-level # ID: tags first
    for file_path in src_dir.rglob("*.py"):
        try:
            content = file_path.read_text("utf-8")
            cleaned, removed = _strip_orphan_ids(content)
            if removed > 0:
                rel_path = str(file_path.relative_to(context.git_service.repo_path))
                result = await executor.execute(
                    action_id="file.tag_metadata",
                    write=write,
                    file_path=rel_path,
                    code=cleaned,
                    allowed_operations=["comment.delete"],
                )
                if result.ok:
                    mode_str = "Removed" if write else "Would remove"
                    logger.info(
                        "   -> [%s] %d orphan ID(s) in %s", mode_str, removed, rel_path
                    )
        except Exception as e:
            logger.error("Error stripping orphan IDs in %s: %s", file_path.name, e)

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
                error_msg = result.data.get("error") or "unknown error"
                violations = result.data.get("violations", [])
                logger.error("   -> [BLOCKED] %s: %s", rel_path, error_msg)
                for violation in violations[:3]:
                    logger.debug("        - %s", violation)

        except Exception as e:
            logger.error("Failed to prepare fix for %s: %s", file_path.name, e)

    logger.info("🏁 ID Assignment complete. Total: %d", total_ids_assigned)
    return total_ids_assigned
