# src/body/atomic/fix/atomic_actions.py

"""fix.atomic_actions — fix atomic-actions pattern violations.

Split from body/atomic/fix_actions.py (one action per module, #806).
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
    action_id="fix.atomic_actions",
    description="Fix atomic actions pattern violations",
    category=ActionCategory.FIX,
    policies=["rules/architecture/atomic_actions"],
    remediates=["atomic_actions.must_return_action_result"],
)
@atomic_action(
    action_id="fix.atomic_actions",
    intent="Atomic action for action_fix_atomic_actions",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 525fff82-3c87-4847-83a5-346ad9c78534
async def action_fix_atomic_actions(
    core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """Fix atomic action patterns."""
    from body.evaluators.atomic_actions_evaluator import AtomicActionsEvaluator
    from body.evaluators.atomic_actions_rules import AtomicActionViolation
    from body.self_healing.atomic_actions_fixer import fix_file_violations

    start_time = time.time()
    root_path = core_context.git_service.repo_path

    evaluator = AtomicActionsEvaluator(context=core_context)
    try:
        result_wrapper = await evaluator.execute(repo_root=root_path)
        data = result_wrapper.data
    except Exception as e:
        return ActionResult(
            action_id="fix.atomic_actions",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start_time,
        )

    if not data["violations"]:
        return ActionResult(
            action_id="fix.atomic_actions", ok=True, data={"violations_fixed": 0}
        )

    violations = [
        AtomicActionViolation(
            file_path=root_path / v["file"],
            function_name=v["function"],
            rule_id=v["rule"],
            message=v["message"],
            severity=v["severity"],
            line_number=v["line"],
            suggested_fix=v.get("suggested_fix"),
        )
        for v in data["violations"]
    ]

    # Left unannotated deliberately: annotating the key type surfaces a latent
    # str/Path confusion in this function (keys are Path, consumed as str). That
    # is a real bug tracked separately, not a mechanical annotation — suppressing
    # the var-annotated finding here would hide it. See #644 (str/Path confusion).
    violations_by_file = {}  # type: ignore[var-annotated]
    for v in violations:
        violations_by_file.setdefault(v.file_path, []).append(v)

    fixes_applied = 0
    files_modified = 0
    files_failed = 0

    for file_path, file_violations in violations_by_file.items():
        try:
            source = file_path.read_text(encoding="utf-8")
            modified_source = fix_file_violations(source, file_violations, file_path)
            if modified_source != source:
                if write:
                    rel_path = str(file_path.relative_to(root_path))
                    core_context.file_handler.write_runtime_text(
                        rel_path, modified_source
                    )
                    files_modified += 1
                fixes_applied += len(file_violations)
        except Exception as e:
            logger.error("Error fixing %s: %s", file_path, e)
            files_failed += 1

    return ActionResult(
        action_id="fix.atomic_actions",
        ok=files_failed == 0,
        data={
            "files_modified": files_modified,
            "violations_fixed": fixes_applied,
            "files_failed": files_failed,
        },
        duration_sec=time.time() - start_time,
    )
