# src/body/atomic/file_ops.py
# ID: atomic.file_ops
"""
Atomic File Operations - Canonical implementation of filesystem mutations.
Governed by safe_by_default and constitutional auditing.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from body.atomic.registry import ActionCategory, register_action
from shared.action_types import ActionImpact, ActionResult
from shared.logger import getLogger
from will.orchestration.validation_pipeline import validate_code_async


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


@register_action(
    action_id="file.read",
    description="Read content from a file safely",
    category=ActionCategory.CHECK,
    policies=["data_governance"],
    impact_level="safe",
)
# ID: 67364654-e490-4100-8488-874e4e9f7331
async def action_read_file(
    file_path: str, core_context: CoreContext, **kwargs
) -> ActionResult:
    """Reads a file from the repository and returns its content in the ActionResult data."""
    start = time.time()
    try:
        # Resolve path safely
        full_path = core_context.git_service.repo_path / file_path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = full_path.read_text(encoding="utf-8")
        return ActionResult(
            action_id="file.read",
            ok=True,
            data={"content": content, "path": file_path},
            duration_sec=time.time() - start,
            impact=ActionImpact.READ_ONLY,
        )
    except Exception as e:
        return ActionResult(
            action_id="file.read",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start,
        )


@register_action(
    action_id="file.create",
    description="Create a new file with validated content",
    category=ActionCategory.BUILD,
    policies=["body_contracts"],
    impact_level="moderate",
)
# ID: 89436454-e590-4100-8488-874e4e9f7331
async def action_create_file(
    file_path: str, code: str, core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """Creates a file. Enforces pre-flight validation before any bytes touch the disk."""
    start = time.time()
    try:
        # 1. Validation (Safe by Default)
        validation_result = await validate_code_async(
            file_path, code, auditor_context=core_context.auditor_context
        )
        if validation_result["status"] == "dirty":
            return ActionResult(
                action_id="file.create",
                ok=False,
                data={
                    "error": "Validation failed",
                    "violations": validation_result["violations"],
                },
                duration_sec=time.time() - start,
            )

        # 2. Apply change if write is requested
        if write:
            core_context.file_handler.write_runtime_text(
                file_path, validation_result["code"]
            )
            if core_context.git_service.is_git_repo():
                core_context.git_service.add(file_path)

        return ActionResult(
            action_id="file.create",
            ok=True,
            data={"path": file_path, "written": write},
            duration_sec=time.time() - start,
            impact=ActionImpact.WRITE_CODE,
        )
    except Exception as e:
        return ActionResult(
            action_id="file.create",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start,
        )


@register_action(
    action_id="file.edit",
    description="Modify an existing file with validated code",
    category=ActionCategory.FIX,
    policies=["body_contracts"],
    impact_level="moderate",
)
# ID: 12364654-e590-4100-8488-874e4e9f7331
async def action_edit_file(
    file_path: str, code: str, core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """Edits a file. Logic is identical to create but identifies as a FIX."""
    return await action_create_file(file_path, code, core_context, write=write)
