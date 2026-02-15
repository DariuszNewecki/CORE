# src/body/atomic/file_ops.py
# ID: 5aa0b8f1-596b-4bdf-9db6-937af0608cb7

"""
Atomic File Operations - Canonical implementation of filesystem mutations.
GOVERNED: Now enforces strict Syntax Validation and Metadata Finalization.
"""

from __future__ import annotations

import ast
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
    action_id="file.create",
    description="Create a new file with validated content",
    category=ActionCategory.BUILD,
    policies=["rules/architecture/atomic_actions"],
    impact_level="moderate",
)
@atomic_action(
    action_id="file.create",
    intent="Create a file with mandatory syntax validation",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: bfa655f7-1eed-4afe-a5d3-90e32ecb6fa5
async def action_create_file(
    file_path: str, code: str, core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """Creates a file. Enforces strict pre-flight syntax and metadata checks."""
    start = time.time()
    try:
        # 1. THE IRON GATE: Syntax Validation
        # If this is a Python file, it MUST parse or we halt immediately.
        if file_path.endswith(".py"):
            try:
                ast.parse(code)
            except SyntaxError as e:
                logger.error(
                    "\u274c CONSTITUTIONAL VIOLATION: AI generated invalid Python in %s",
                    file_path,
                )
                return ActionResult(
                    action_id="file.create",
                    ok=False,
                    data={
                        "error": "Syntax Error: Refusing to write invalid Python code.",
                        "details": str(e),
                        "line": e.lineno,
                    },
                    duration_sec=time.time() - start,
                )

        # 2. THE FINALIZER: Auto-Metadata
        # If the write is approved, we ensure the 'Paperwork' is done.
        # This is handled by the FileHandler inside the write_runtime_text call.

        if write:
            # We use the governed mutation surface
            core_context.file_handler.write_runtime_text(file_path, code)
            if core_context.git_service.is_git_repo():
                core_context.git_service.add(file_path)

        return ActionResult(
            action_id="file.create",
            ok=True,
            data={
                "path": file_path,
                "written": write,
                "status": "Verified & Persisted" if write else "Verified (Dry Run)",
            },
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
    policies=["rules/architecture/atomic_actions"],
    impact_level="moderate",
)
@atomic_action(
    action_id="file.edit",
    intent="Edit a file with mandatory syntax validation",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 3044d199-3315-4e2c-8f0f-9e7cb630602f
async def action_edit_file(
    file_path: str, code: str, core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """Edits a file. Reuses creation logic to ensure identical safety gates."""
    return await action_create_file(file_path, code, core_context, write=write)


@register_action(
    action_id="file.read",
    description="Read content from a file safely",
    category=ActionCategory.CHECK,
    policies=["rules/data/governance"],
    impact_level="safe",
)
@atomic_action(
    action_id="file.read",
    intent="Read file for context",
    impact=ActionImpact.READ_ONLY,
    policies=["atomic_actions"],
)
# ID: 63f1cf2a-b2c1-4886-8f74-89a81dbc95ff
async def action_read_file(
    file_path: str, core_context: CoreContext, **kwargs
) -> ActionResult:
    """Reads a file from the repository."""
    start = time.time()
    try:
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
