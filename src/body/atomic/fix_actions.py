# src/body/atomic/fix_actions.py

"""
Atomic Fix Actions - Code Remediation

Each action does ONE thing and returns ActionResult.
Actions are composable, auditable, and constitutionally governed.

Constitutional Alignment:
- Boundary: Uses CoreContext for repo_path (no direct settings access)
- Circularity Fix: Feature-level imports are performed inside functions.

HEALED (V2.7.2):
- Context Injection: Now correctly passes core_context to AtomicActionsEvaluator
  to prevent 'NoneType' attribute errors during self-healing.

HEALED (V2.7.4):
- Registry Gap: Added fix.duplicate_ids to the atomic registry.
- Policy References: All policies now use canonical indexed IDs
  (rules/<domain>/<name>) matching IntentRepository index.
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
    action_id="fix.format",
    description="Format code with Black and Ruff",
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
    impact_level="safe",
)
@atomic_action(
    action_id="format.code",
    intent="Atomic action for action_format_code",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 5c3ede6c-23e1-4b92-8a00-7b2046eac121
async def action_format_code(write: bool = False) -> ActionResult:
    """Format code using Black and Ruff."""
    start = time.time()
    from features.self_healing.code_style_service import format_code

    format_code(write=write)
    return ActionResult(
        action_id="fix.format",
        ok=True,
        data={"formatted": True, "write": write},
        duration_sec=time.time() - start,
    )


@register_action(
    action_id="fix.imports",
    description="Sort and group imports according to PEP 8 / Constitutional standards",
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
    impact_level="safe",
)
@atomic_action(
    action_id="fix.imports",
    intent="Standardize Python import blocks using Ruff",
    impact=ActionImpact.WRITE_METADATA,
    policies=["atomic_actions"],
)
# ID: d5879178-fdfe-4d8b-b6a6-f887f8e9500b
async def action_fix_imports(write: bool = False) -> ActionResult:
    """Sort and group Python imports according to constitutional style policy."""
    start = time.time()
    from shared.utils.subprocess_utils import run_poetry_command

    target_path = "src/"
    try:
        cmd = ["ruff", "check", target_path, "--select", "I"]
        if write:
            cmd.append("--fix")
        cmd.append("--exit-zero")

        # Execute via sanctioned subprocess utility
        run_poetry_command(f"Sorting imports in {target_path}", cmd)

        return ActionResult(
            action_id="fix.imports",
            ok=True,
            data={"status": "completed", "target": target_path, "write": write},
            duration_sec=time.time() - start,
        )
    except Exception as e:
        return ActionResult(
            action_id="fix.imports",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start,
        )


@register_action(
    action_id="fix.docstrings",
    description="Fix missing or malformed docstrings",
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
    impact_level="safe",
)
@atomic_action(
    action_id="fix.docstrings",
    intent="Atomic action for action_fix_docstrings",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 3024996b-c84e-4b81-b542-205e7b370102
async def action_fix_docstrings(
    core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """Fix docstrings across the repository."""
    start = time.time()
    from features.self_healing.docstring_service import fix_docstrings

    await fix_docstrings(context=core_context, write=write)
    return ActionResult(
        action_id="fix.docstrings",
        ok=True,
        data={"status": "completed", "write": write},
        duration_sec=time.time() - start,
    )


@register_action(
    action_id="fix.headers",
    description="Fix file headers to match constitutional standards",
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
    impact_level="safe",
)
@atomic_action(
    action_id="fix.headers",
    intent="Atomic action for action_fix_headers",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 7d43d782-739a-47d3-ae3e-c36047ad9867
async def action_fix_headers(
    core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """Fix file headers."""
    from body.cli.commands.fix.code_style import fix_headers_internal

    return await fix_headers_internal(core_context, write=write)


@register_action(
    action_id="fix.ids",
    description="Add missing ID tags to functions and classes",
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
    impact_level="safe",
)
@atomic_action(
    action_id="fix.ids",
    intent="Atomic action for action_fix_ids",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 854f5010-aaec-4f14-8d72-3e3070334c54
async def action_fix_ids(
    core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """Fix missing ID tags."""
    from body.cli.commands.fix.metadata import fix_ids_internal

    return await fix_ids_internal(core_context, write=write)


@register_action(
    action_id="fix.duplicate_ids",
    description="Resolve duplicate UUID collisions across source files",
    category=ActionCategory.FIX,
    policies=["rules/code/linkage"],
    impact_level="moderate",
)
@atomic_action(
    action_id="fix.duplicate_ids",
    intent="Resolve duplicate ID conflicts by regenerating UUIDs",
    impact=ActionImpact.WRITE_METADATA,
    policies=["id_uniqueness_check"],
)
# ID: 2e7f8a1b-c3d4-4e5f-96a0-b1d2e3f4a5b6
async def action_fix_duplicate_ids(
    core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """Resolve duplicate UUID collisions in source files."""
    from body.cli.commands.fix.metadata import fix_duplicate_ids_internal

    return await fix_duplicate_ids_internal(core_context, write=write)


@register_action(
    action_id="fix.logging",
    description="Replace print statements with proper logging",
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
    impact_level="safe",
)
@atomic_action(
    action_id="fix.logging",
    intent="Atomic action for action_fix_logging",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 7661f20f-3d41-4501-a0ab-c30804d29ad0
async def action_fix_logging(
    core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """Fix logging violations."""
    start = time.time()
    from body.cli.commands.fix_logging import LoggingFixer

    fixer = LoggingFixer(
        repo_root=core_context.git_service.repo_path,
        file_handler=core_context.file_handler,
        dry_run=not write,
    )
    result = fixer.fix_all()
    return ActionResult(
        action_id="fix.logging",
        ok=True,
        data=result,
        duration_sec=time.time() - start,
    )


@register_action(
    action_id="fix.placeholders",
    description="Replace FUTURE/PENDING placeholders",
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
    impact_level="moderate",
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
    """Fix placeholder comments."""
    start = time.time()
    from features.self_healing.placeholder_fixer_service import (
        fix_placeholders_in_content,
    )

    files_modified = 0
    repo_root = core_context.git_service.repo_path
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
            data={"files_affected": files_modified, "written": write},
            duration_sec=time.time() - start,
        )
    except Exception as e:
        return ActionResult(
            action_id="fix.placeholders", ok=False, data={"error": str(e)}
        )


@register_action(
    action_id="fix.atomic_actions",
    description="Fix atomic actions pattern violations",
    category=ActionCategory.FIX,
    policies=["rules/architecture/atomic_actions"],
    impact_level="moderate",
)
@atomic_action(
    action_id="fix.atomic",
    intent="Atomic action for action_fix_atomic_actions",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 525fff82-3c87-4847-83a5-346ad9c78534
async def action_fix_atomic_actions(
    core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """Fix atomic action patterns."""
    from body.cli.commands.fix.atomic_actions import _fix_file_violations
    from body.evaluators.atomic_actions_evaluator import (
        AtomicActionsEvaluator,
        AtomicActionViolation,
    )

    start_time = time.time()
    root_path = core_context.git_service.repo_path

    # HEALED: Pass the context to the Evaluator so it can initialize its tracer properly
    evaluator = AtomicActionsEvaluator(context=core_context)

    result_wrapper = await evaluator.execute(repo_root=root_path)
    data = result_wrapper.data

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

    violations_by_file = {}
    for v in violations:
        violations_by_file.setdefault(v.file_path, []).append(v)

    fixes_applied = 0
    files_modified = 0

    for file_path, file_violations in violations_by_file.items():
        try:
            source = file_path.read_text(encoding="utf-8")
            modified_source = _fix_file_violations(source, file_violations, file_path)
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

    return ActionResult(
        action_id="fix.atomic_actions",
        ok=True,
        data={"files_modified": files_modified, "violations_fixed": fixes_applied},
        duration_sec=time.time() - start_time,
    )
