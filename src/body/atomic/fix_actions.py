# src/body/atomic/fix_actions.py
# ID: atomic.fix
"""
Atomic Fix Actions - Code Remediation

Each action does ONE thing and returns ActionResult.
Actions are composable, auditable, and constitutionally governed.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from body.atomic.registry import ActionCategory, register_action


if TYPE_CHECKING:
    from shared.context import CoreContext

from body.cli.commands.fix.code_style import fix_headers_internal
from body.cli.commands.fix.metadata import fix_ids_internal
from body.cli.commands.fix_logging import LoggingFixer
from features.self_healing.code_style_service import format_code
from features.self_healing.docstring_service import fix_docstrings
from features.self_healing.placeholder_fixer_service import fix_placeholders_in_content
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)


@register_action(
    action_id="fix.format",
    description="Format code with Black and Ruff",
    category=ActionCategory.FIX,
    policies=["code_quality_standards"],
    impact_level="safe",
)
@atomic_action(
    action_id="format.code",
    intent="Atomic action for action_format_code",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: b52fd580-bb76-44d9-a9bd-14d1de6c1bfe
async def action_format_code(write: bool = False) -> ActionResult:
    """
    Format code using Black and Ruff.
    """
    start = time.time()

    # CONSTITUTIONAL FIX: Pass the write flag to the service!
    format_code(write=write)

    return ActionResult(
        action_id="fix.format",
        ok=True,
        data={"formatted": True, "write": write},
        duration_sec=time.time() - start,
    )


@register_action(
    action_id="fix.docstrings",
    description="Fix missing or malformed docstrings",
    category=ActionCategory.FIX,
    policies=["code_quality_standards"],
    impact_level="safe",
)
@atomic_action(
    action_id="fix.docstrings",
    intent="Atomic action for action_fix_docstrings",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: c3d4e5f6-a7b8-9c0d-1e2f-3a4b5c6d7e8f
async def action_fix_docstrings(
    core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """
    Fix docstrings across the repository.
    """
    start = time.time()
    # fix_docstrings is async and takes context + write
    result = await fix_docstrings(context=core_context, write=write)

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
    policies=["header_compliance"],
    impact_level="safe",
)
@atomic_action(
    action_id="fix.headers",
    intent="Atomic action for action_fix_headers",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: d4e5f6a7-b8c9-0d1e-2f3a-4b5c6d7e8f9a
async def action_fix_headers(
    core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """
    Fix file headers.
    """
    # fix_headers_internal takes context and write (not dry_run)
    return await fix_headers_internal(core_context, write=write)


@register_action(
    action_id="fix.ids",
    description="Add missing ID tags to functions and classes",
    category=ActionCategory.FIX,
    policies=["code_quality_standards"],
    impact_level="safe",
)
@atomic_action(
    action_id="fix.ids",
    intent="Atomic action for action_fix_ids",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: e5f6a7b8-c9d0-1e2f-3a4b-5c6d7e8f9a0b
async def action_fix_ids(
    core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """
    Fix missing ID tags.
    """
    # fix_ids_internal takes context and write (not dry_run)
    return await fix_ids_internal(core_context, write=write)


@register_action(
    action_id="fix.logging",
    description="Replace print statements with proper logging",
    category=ActionCategory.FIX,
    policies=["code_quality_standards"],
    impact_level="safe",
)
@atomic_action(
    action_id="fix.logging",
    intent="Atomic action for action_fix_logging",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: f6a7b8c9-d0e1-2f3a-4b5c-6d7e8f9a0b1c
async def action_fix_logging(
    core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """
    Fix logging violations.
    """
    start = time.time()
    # LoggingFixer takes repo_root, file_handler, and dry_run
    fixer = LoggingFixer(
        repo_root=settings.REPO_PATH,
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
    description="Replace FUTURE/PENDING placeholders with proper implementations",
    category=ActionCategory.FIX,
    policies=["code_quality_standards"],
    impact_level="moderate",
)
@atomic_action(
    action_id="fix.placeholders",
    intent="Atomic action for action_fix_placeholders",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 3c8e9d7f-6a5b-4e3c-9d2f-8b7e6a5f4d3c
async def action_fix_placeholders(
    core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """
    Fix placeholder comments.
    """
    start = time.time()
    files_modified = 0
    repo_root = core_context.git_service.repo_path

    try:
        src_dir = repo_root / "src"
        for py_file in src_dir.rglob("*.py"):
            original = py_file.read_text(encoding="utf-8")
            fixed = fix_placeholders_in_content(original)

            if fixed != original:
                if write:
                    # CONSTITUTIONAL FIX: Use governed mutation surface
                    rel_path = str(py_file.relative_to(repo_root))
                    core_context.file_handler.write_runtime_text(rel_path, fixed)
                files_modified += 1

        return ActionResult(
            action_id="fix.placeholders",
            ok=True,
            data={
                "files_affected": files_modified,
                "written": write,
                "dry_run": not write,
            },
            duration_sec=time.time() - start,
        )
    except Exception as e:
        logger.error("Placeholder fix failed: %s", e, exc_info=True)
        return ActionResult(
            action_id="fix.placeholders",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start,
        )


@register_action(
    action_id="fix.atomic_actions",
    description="Fix atomic actions pattern violations automatically",
    category=ActionCategory.FIX,
    policies=["atomic_actions"],
    impact_level="moderate",
)
# ID: 4f8e9d7c-6a5b-3e2f-9c8d-7b6e9f4a8c7e
@atomic_action(
    action_id="fix.atomic",
    intent="Atomic action for action_fix_atomic_actions",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 4bfef676-3954-45e2-adb5-247103e47f27
async def action_fix_atomic_actions(
    core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """
    Headless logic to fix atomic action patterns.
    """
    import asyncio

    # Import helper from command file and evaluator
    from body.cli.commands.fix.atomic_actions import _fix_file_violations
    from body.evaluators.atomic_actions_evaluator import (
        AtomicActionsEvaluator,
        AtomicActionViolation,
    )

    start_time = time.time()
    root_path = core_context.git_service.repo_path

    # Use Evaluator instead of Checker
    evaluator = AtomicActionsEvaluator()
    result_wrapper = await evaluator.execute(repo_root=root_path)
    data = result_wrapper.data

    if not data["violations"]:
        return ActionResult(
            action_id="fix.atomic_actions",
            ok=True,
            data={"violations_fixed": 0, "files_modified": 0},
            duration_sec=time.time() - start_time,
        )

    # Convert violation dicts back to objects for helper function
    violations = [
        AtomicActionViolation(
            file_path=root_path / v["file"],
            function_name=v["function"],
            rule_id=v["rule"],
            message=v["message"],
            severity=v["severity"],
            line_number=v["line"],
            suggested_fix=v["suggested_fix"],
        )
        for v in data["violations"]
    ]

    # Group by file
    violations_by_file = {}
    for v in violations:
        violations_by_file.setdefault(v.file_path, []).append(v)

    fixes_applied = 0
    files_modified = 0

    for file_path, file_violations in violations_by_file.items():
        try:
            source = await asyncio.to_thread(file_path.read_text, encoding="utf-8")
            modified_source = _fix_file_violations(source, file_violations, file_path)

            if modified_source != source:
                if write:
                    # Use governed FileHandler from context
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
        data={
            "files_modified": files_modified,
            "violations_fixed": fixes_applied,
            "dry_run": not write,
        },
        duration_sec=time.time() - start_time,
    )
