# src/body/atomic/fix/placeholders.py

"""fix.placeholders — replace FUTURE/PENDING placeholders.

Split from body/atomic/fix_actions.py (one action per module, #806).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from body.atomic.fix._shared import _error_data
from body.atomic.registry import ActionCategory, register_action
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


@register_action(
    action_id="fix.placeholders",
    description="Replace FUTURE/PENDING placeholders",
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
    remediates=[],  # ADR-114: purity.no_todo_placeholders retired
)
@atomic_action(
    action_id="fix.placeholders",
    intent="Atomic action for action_fix_placeholders",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: fc997ae2-05e6-4823-81dd-e645afee2a7e
async def action_fix_placeholders(
    core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """Replace placeholder comments.

    Two invocation modes:

    1. Targeted (autonomous loop): caller supplies ``file_path`` in kwargs
       (ViolationRemediatorWorker threads this through ``ProposalAction.parameters``).
       The action operates on exactly that file. This matches the action's
       ``"safe"`` classification — bounded scope per invocation.

    2. Sweep (legacy CLI): no ``file_path`` supplied. The action walks every
       ``*.py`` under ``src/``. This mode is preserved for backwards
       compatibility with ``cli.commands.fix_placeholders`` but emits a
       warning so any remaining unbounded autonomous callers are visible.

    On IntentGuard rejection the handler uses ``_error_data`` to persist the
    structured ``ConstitutionalViolationError.to_dict()`` payload — ``rule_name``,
    ``path``, ``source_policy`` survive into ``proposal.execution_results``
    instead of collapsing to a flat error string.
    """
    start = time.time()
    from body.self_healing.placeholder_fixer_service import (
        fix_placeholders_in_content,
    )

    repo_root: Path = core_context.git_service.repo_path
    file_path = kwargs.get("file_path")

    # ---- Targeted mode ------------------------------------------------------
    if file_path:
        try:
            target_rel = str(file_path).lstrip("./")
            target_abs = (repo_root / target_rel).resolve()

            # Keep the action bounded to src/ — refuse anything outside it.
            src_root = (repo_root / "src").resolve()
            try:
                target_abs.relative_to(src_root)
            except ValueError:
                return ActionResult(
                    action_id="fix.placeholders",
                    ok=False,
                    data={
                        "error": f"Target outside src/ scope: {target_rel}",
                        "file_path": target_rel,
                    },
                    duration_sec=time.time() - start,
                )

            if not target_abs.is_file() or target_abs.suffix != ".py":
                return ActionResult(
                    action_id="fix.placeholders",
                    ok=False,
                    data={
                        "error": f"Target is not a .py file: {target_rel}",
                        "file_path": target_rel,
                    },
                    duration_sec=time.time() - start,
                )

            original = target_abs.read_text(encoding="utf-8")
            fixed = fix_placeholders_in_content(original)

            if fixed == original:
                return ActionResult(
                    action_id="fix.placeholders",
                    ok=True,
                    data={
                        "files_affected": 0,
                        "written": False,
                        "file_path": target_rel,
                        "note": "no placeholders found",
                    },
                    duration_sec=time.time() - start,
                )

            if write:
                core_context.file_handler.write_runtime_text(target_rel, fixed)

            return ActionResult(
                action_id="fix.placeholders",
                ok=True,
                data={
                    "files_affected": 1,
                    "written": write,
                    "file_path": target_rel,
                },
                duration_sec=time.time() - start,
            )
        except Exception as e:
            return ActionResult(
                action_id="fix.placeholders",
                ok=False,
                data=_error_data(e, file_path=str(file_path)),
                duration_sec=time.time() - start,
            )

    # ---- Sweep mode (CLI callers only) -------------------------------------
    logger.warning(
        "fix.placeholders invoked in sweep mode (no file_path). "
        "This mode is reserved for CLI callers; autonomous callers MUST "
        "supply file_path to stay within their declared impact scope."
    )

    files_modified = 0
    try:
        src_dir = repo_root / "src"
        for py_file in src_dir.rglob("*.py"):
            original = py_file.read_text(encoding="utf-8")
            fixed = fix_placeholders_in_content(original)
            if fixed != original:
                if write:
                    rel_path = str(py_file.relative_to(repo_root))
                    core_context.file_handler.write_runtime_text(rel_path, fixed)
                files_modified += 1
        return ActionResult(
            action_id="fix.placeholders",
            ok=True,
            data={"files_affected": files_modified, "written": write, "mode": "sweep"},
            duration_sec=time.time() - start,
        )
    except Exception as e:
        return ActionResult(
            action_id="fix.placeholders",
            ok=False,
            data=_error_data(e, mode="sweep"),
            duration_sec=time.time() - start,
        )
