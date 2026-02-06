# src/body/atomic/metadata_ops.py
# ID: TBD

"""
Atomic Metadata Operations — governed file mutations that preserve executable semantics.

This action provides a WRITE_METADATA pathway that:
1. Proves the mutation is metadata-only (normalized AST comparison)
2. Passes WRITE_METADATA impact tier to FileHandler/IntentGuard
3. Applies to ALL src/**/*.py files (no exclusion lists needed)
4. Writes via FileHandler (IntentGuard still blocks .intent/**)

Used by: fix.ids, fix.docstrings, fix.headers
NOT used by: file.edit, file.create (those are WRITE_CODE)
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
    action_id="file.tag_metadata",
    description="Modify a file with metadata-only changes (comments, docstrings, IDs). "
    "Proves semantic preservation via normalized AST comparison.",
    category=ActionCategory.FIX,
    policies=["rules.code.metadata_mutations"],
    impact_level="safe",
)
@atomic_action(
    action_id="file.tag_metadata",
    intent="Apply metadata-only mutations with semantic preservation proof",
    impact=ActionImpact.WRITE_METADATA,
    policies=["rules.code.metadata_mutations"],
)
# ID: TBD
# ID: b89b0899-f654-4a76-b0db-f2c183c6caa7
async def action_tag_metadata(
    file_path: str,
    code: str,
    core_context: CoreContext,
    write: bool = False,
    allowed_operations: list[str] | None = None,
    max_comment_length: int = 120,
    **kwargs,
) -> ActionResult:
    """
    Apply a metadata-only mutation to a file.

    This action:
    1. Reads the original file content
    2. Proves the diff is metadata-only (AST invariant)
    3. Validates operation constraints (comment length, allowed ops)
    4. Writes via FileHandler with WRITE_METADATA impact tier

    Args:
        file_path: Repo-relative path (e.g. "src/features/self_healing/foo.py")
        code: The complete new file content
        core_context: CoreContext with file_handler and git_service
        write: If True, apply changes. If False, dry-run with proof.
        allowed_operations: List of permitted operation types.
            e.g. ["comment.insert"] for fix.ids
            e.g. ["comment.insert", "comment.replace"] for fix.headers
            e.g. ["docstring.insert", "docstring.replace"] for fix.docstrings
            If None, all metadata operations are permitted.
        max_comment_length: Maximum length for new comment lines (default 120).

    Returns:
        ActionResult with proof details in data.
    """
    # LAZY IMPORT: Breaks circular dependency body.atomic -> mind.logic.engines
    from mind.logic.engines.ast_gate.checks.metadata_checks import (
        verify_metadata_only_diff,
    )

    start = time.time()

    try:
        # 1. Read original content
        full_path = core_context.git_service.repo_path / file_path
        if not full_path.exists():
            return ActionResult(
                action_id="file.tag_metadata",
                ok=False,
                data={"error": f"File not found: {file_path}"},
                duration_sec=time.time() - start,
            )

        original_code = full_path.read_text(encoding="utf-8")

        # 2. Short-circuit: no change
        if original_code == code:
            return ActionResult(
                action_id="file.tag_metadata",
                ok=True,
                data={"path": file_path, "written": False, "reason": "no_change"},
                duration_sec=time.time() - start,
                impact=ActionImpact.READ_ONLY,
            )

        # 3. CONSTITUTIONAL PROOF: verify metadata-only diff
        proof_params = {"max_comment_length": max_comment_length}
        if allowed_operations is not None:
            proof_params["allowed_operations"] = allowed_operations

        violations = verify_metadata_only_diff(original_code, code, proof_params)

        if violations:
            logger.warning("Metadata proof FAILED for %s: %s", file_path, violations[0])
            return ActionResult(
                action_id="file.tag_metadata",
                ok=False,
                data={
                    "error": "Metadata proof failed",
                    "violations": violations,
                    "path": file_path,
                },
                duration_sec=time.time() - start,
            )

        # 4. Write if requested (via governed FileHandler with WRITE_METADATA impact)
        if write:
            core_context.file_handler.write_runtime_text(
                file_path, code, impact=ActionImpact.WRITE_METADATA.value
            )
            if core_context.git_service.is_git_repo():
                core_context.git_service.add(file_path)

        return ActionResult(
            action_id="file.tag_metadata",
            ok=True,
            data={
                "path": file_path,
                "written": write,
                "proof": "normalized_ast_identical",
                "code": code,
            },
            duration_sec=time.time() - start,
            impact=ActionImpact.WRITE_METADATA,
        )

    except Exception as e:
        logger.error("file.tag_metadata failed for %s: %s", file_path, e)
        return ActionResult(
            action_id="file.tag_metadata",
            ok=False,
            data={"error": str(e), "path": file_path},
            duration_sec=time.time() - start,
        )
