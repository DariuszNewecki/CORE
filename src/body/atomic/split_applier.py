# src/body/atomic/split_applier.py
"""
refactor.apply_split — Apply pre-computed split results to the filesystem.

Routes deterministic ModularitySplitter output through ActionExecutor so
writes are governed and the production set is declared for audit (ADR-101 D2).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from body.atomic.registry import ActionCategory, register_action
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


@register_action(
    action_id="refactor.apply_split",
    description="Write pre-computed deterministic split results to the filesystem",
    category=ActionCategory.FIX,
    policies=["rules/architecture/modularity"],
    remediates=[],
)
@atomic_action(
    action_id="refactor.apply_split",
    intent=(
        "Apply pre-computed SplitResult files: write new modules, "
        "remove the original monolith."
    ),
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 9654b629-246b-411f-9455-a9456a43f4a4
async def action_refactor_apply_split(
    core_context: CoreContext,
    split_results: list,
    write: bool = False,
    **kwargs,
) -> ActionResult:
    """
    Write split_results to disk.

    split_results is a list of dicts from the code_generation phase:
        [{"ok": bool, "split_result": SplitResult}, ...]

    Each SplitResult carries:
        .files          — list of (absolute Path, content str) tuples
        .original_path  — absolute Path to the monolith being replaced

    Nothing is written when write=False (dry-run).
    Returns ActionResult with files_produced populated for commit_proposal_changes
    (ADR-101 D2 production-set derivation).
    """
    start = time.time()
    file_handler = core_context.file_handler
    repo_root = core_context.git_service.repo_path
    files_written: list[str] = []
    files_deleted: list[str] = []

    for entry in split_results:
        if not entry.get("ok"):
            continue
        split_result = entry.get("split_result")
        if split_result is None:
            continue

        if not write:
            for file_path, _content in split_result.files:
                logger.info("Dry-run: would write %s", file_path)
            if split_result.original_path.exists():
                logger.info("Dry-run: would delete %s", split_result.original_path)
            continue

        for file_path, content in split_result.files:
            rel_path = str(file_path.relative_to(repo_root))
            file_handler.write_runtime_text(rel_path, content)
            files_written.append(rel_path)
            logger.info("Wrote split module: %s", rel_path)

        if split_result.original_path.exists():
            rel_original = str(split_result.original_path.relative_to(repo_root))
            file_handler.remove_file(rel_original)
            files_deleted.append(rel_original)
            logger.info("Removed original: %s", rel_original)

    ok = bool(files_written) if write else True
    return ActionResult(
        action_id="refactor.apply_split",
        ok=ok,
        data={
            "files_written": files_written,
            "files_deleted": files_deleted,
            # files_produced is the ADR-101 D2 production-set declaration;
            # includes both new modules and the removed monolith so the commit
            # set and rollback target are complete.
            "files_produced": files_written + files_deleted,
        },
        impact=ActionImpact.WRITE_CODE,
        duration_sec=time.time() - start,
    )
