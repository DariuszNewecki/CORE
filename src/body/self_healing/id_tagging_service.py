# src/body/self_healing/id_tagging_service.py

"""
Provides a service to find and assign missing constitutional ID anchors to public symbols.
Refactored to use the canonical ActionExecutor Gateway for all mutations.
"""

from __future__ import annotations

import ast
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from body.atomic.executor import ActionExecutor
from shared.action_types import ActionImpact, ActionResult
from shared.ast_utility import find_orphan_id_lines, find_symbol_id_and_def_line
from shared.atomic_action import atomic_action
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


def _is_public(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> bool:
    """Determines if a symbol is public (not starting with _ or a dunder)."""
    is_dunder = node.name.startswith("__") and node.name.endswith("__")
    return not node.name.startswith("_") and (not is_dunder)


@dataclass
# ID: f716d02f-4322-4391-a10f-1caef337c31d
class OrphanAnchor:
    """A ``# ID:`` line that annotates no def/class (linkage.no_orphan_ids).

    ``symbol`` is set when a public symbol lacking an ID sits directly below
    the orphan (across blank lines, comments or decorators only): the anchor
    is almost certainly that symbol's own identity, split from it. fix.ids
    leaves the bytes untouched and skips assigning that symbol a fresh ID --
    regenerating would discard the identity the rule exists to preserve.
    """

    file_path: str
    line_number: int
    text: str
    symbol: str | None = None


@dataclass
# ID: 388b5db1-13a1-4d8c-9208-ee50168d440c
class IdAssignmentReport:
    """Outcome of one fix.ids pass: what was assigned, what needs a human."""

    ids_assigned: int = 0
    orphan_anchors: list[OrphanAnchor] = field(default_factory=list)

    @property
    def reattachment_required(self) -> list[OrphanAnchor]:
        """Orphans that shadow a symbol fix.ids therefore refused to re-tag."""
        return [o for o in self.orphan_anchors if o.symbol is not None]


def _orphan_shadowing(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    def_line: int,
    lines: list[str],
    orphan_linenos: set[int],
) -> int | None:
    """Return the orphan anchor line that most plausibly belongs to ``node``.

    Either an orphan inside the symbol's own span (between its first
    decorator and the def line -- e.g. an anchor followed by a blank line),
    or one reached by walking upward from the span over blank lines and
    ordinary comments only. Any other line ends the search. 1-based.
    """
    span_start = min((d.lineno for d in node.decorator_list), default=def_line)
    inside = [n for n in orphan_linenos if span_start <= n < def_line]
    if inside:
        return max(inside)
    i = span_start - 1
    while i >= 1:
        if i in orphan_linenos:
            return i
        stripped = lines[i - 1].strip()
        if stripped and not stripped.startswith("#"):
            return None
        i -= 1
    return None


# ID: 17328e3a-5e37-48ff-94d4-c3f4697825d5
async def assign_missing_ids(
    context: CoreContext, write: bool = False
) -> IdAssignmentReport:
    """
    Scans all Python files in src/ and assigns missing # ID: anchors to public
    symbols via ActionExecutor.

    Orphaned anchors (linkage.no_orphan_ids) are detected with the shared
    helper and left byte-for-byte untouched: they are reported for manual
    re-attachment, never stripped, and a public symbol sitting directly
    below one is NOT given a fresh ID -- that would regenerate an identity
    the orphan still carries. Unrelated missing IDs are still assigned.

    Args:
        context: CoreContext (Required for ActionExecutor)
        write: If True, apply changes; if False, perform dry-run.

    Returns:
        IdAssignmentReport: ids assigned or proposed, plus every orphan found.
    """
    logger.info("🔍 Scanning for missing Constitutional IDs...")

    executor = ActionExecutor(context)
    repo_path = context.git_service.repo_path
    src_dir = repo_path / "src"
    report = IdAssignmentReport()
    files_to_fix: dict[Path, list[dict[str, Any]]] = defaultdict(list)

    if not src_dir.exists():
        logger.warning("Source directory not found: %s", src_dir)
        return report

    # 1. Discovery Phase (AST scan + orphan detection, read-only)
    for file_path in src_dir.rglob("*.py"):
        try:
            content = file_path.read_text("utf-8")
            source_lines = content.splitlines()
            rel_path = str(file_path.relative_to(repo_path))

            orphans = {
                lineno: OrphanAnchor(rel_path, lineno, text)
                for lineno, text in find_orphan_id_lines(content)
            }

            tree = ast.parse(content, filename=str(file_path))
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    if not _is_public(node):
                        continue

                    id_result = find_symbol_id_and_def_line(node, source_lines)
                    if id_result.has_id:
                        continue

                    shadow = _orphan_shadowing(
                        node, id_result.definition_line_num, source_lines, set(orphans)
                    )
                    if shadow is not None:
                        orphans[shadow].symbol = node.name
                        continue

                    files_to_fix[file_path].append(
                        {
                            "line_number": id_result.definition_line_num,
                            "name": node.name,
                        }
                    )

            for orphan in orphans.values():
                report.orphan_anchors.append(orphan)
                logger.warning(
                    "   -> [ORPHAN] %s:%d %s annotates no def/class%s; requires "
                    "manual re-attachment (linkage.no_orphan_ids) -- left untouched",
                    orphan.file_path,
                    orphan.line_number,
                    orphan.text.strip(),
                    f" (public '{orphan.symbol}' below it not re-tagged)"
                    if orphan.symbol
                    else "",
                )
        except Exception as e:
            logger.error("Error analyzing %s: %s", file_path.name, e)

    if not files_to_fix:
        logger.info("✅ All public symbols have constitutional IDs.")
        return report

    # 2. Execution Phase (Gateway dispatch)
    for file_path, fixes in files_to_fix.items():
        # Sort by line number descending to prevent line-shift errors during insertion
        fixes.sort(key=lambda x: int(x["line_number"]), reverse=True)

        try:
            rel_path = str(file_path.relative_to(repo_path))
            lines = file_path.read_text("utf-8").splitlines()

            for fix in fixes:
                line_index = int(fix["line_number"]) - 1
                original_line = lines[line_index]
                indentation = len(original_line) - len(original_line.lstrip(" "))
                new_id = str(uuid.uuid4())
                tag_line = f"{' ' * indentation}# ID: {new_id}"
                lines.insert(line_index, tag_line)
                report.ids_assigned += 1

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

    logger.info("🏁 ID Assignment complete. Total: %d", report.ids_assigned)
    return report


@atomic_action(
    action_id="fix.ids",
    intent="Assign stable UUIDs to untagged public symbols",
    impact=ActionImpact.WRITE_METADATA,
    policies=["symbol_identification"],
    category="fixers",
)
# ID: 2d37fcb6-863e-4197-a3b8-88ad54a2b99c
async def fix_ids_internal(
    context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """
    Core orchestrator for fix.ids — moved from cli/commands/fix/metadata.py
    under ADR-050. Wraps assign_missing_ids in an ActionResult envelope.
    """
    start_time = time.time()
    try:
        report = await assign_missing_ids(context, write=write)
        total_assigned = report.ids_assigned
        return ActionResult(
            action_id="fix.ids",
            ok=True,
            data={
                "ids_assigned": total_assigned,
                "files_processed": 1 if total_assigned > 0 else 0,
                "dry_run": not write,
                "mode": "write" if write else "dry-run",
                # linkage.no_orphan_ids: detected, never mutated. Each entry
                # needs a human to re-attach the anchor to its symbol.
                "orphan_anchors": [
                    {
                        "file_path": o.file_path,
                        "line_number": o.line_number,
                        "id_line": o.text.strip(),
                        "shadowed_symbol": o.symbol,
                    }
                    for o in report.orphan_anchors
                ],
                "reattachment_required": len(report.reattachment_required),
            },
            duration_sec=time.time() - start_time,
            impact=ActionImpact.WRITE_METADATA,
        )
    except Exception as e:
        return ActionResult(
            action_id="fix.ids",
            ok=False,
            data={"error": str(e), "error_type": type(e).__name__},
            duration_sec=time.time() - start_time,
            logs=[f"Exception during ID assignment: {e}"],
        )
