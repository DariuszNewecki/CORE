# src/body/atomic/fix_actions.py
# ID: atomic.fix
"""
Atomic Fix Actions - Code Remediation

Each action does ONE thing and returns ActionResult.
Actions are composable, auditable, and constitutionally governed.

CONSTITUTIONAL COMPLIANCE:
- Enforces governance.logic_mutation.governed by using FileHandler.
- Uses ActionExecutor Gateway logic for all mutations.
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
# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
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
    try:
        logger.info("Starting code formatting (Black + Ruff)")

        if write:
            format_code(path=None)  # Format entire project
            files_changed = 1
        else:
            files_changed = 0

        return ActionResult(
            action_id="fix.format",
            ok=True,
            data={
                "files_changed": files_changed,
                "dry_run": not write,
            },
            duration_sec=time.time() - start,
        )
    except Exception as e:
        logger.error("Code formatting failed: %s", e, exc_info=True)
        return ActionResult(
            action_id="fix.format",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start,
        )


@register_action(
    action_id="fix.ids",
    description="Assign constitutional IDs to functions/classes",
    category=ActionCategory.FIX,
    policies=["constitutional_header_policy"],
    impact_level="safe",
)
# ID: b2c3d4e5-f678-90ab-cdef-1234567890ab
@atomic_action(
    action_id="fix.ids",
    intent="Atomic action for action_fix_ids",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: ce9fbde9-dc32-46bd-a9ac-f96b8a7fec55
async def action_fix_ids(
    core_context: CoreContext, write: bool = False
) -> ActionResult:
    """
    Assign unique IDs to all functions and classes.
    """
    start = time.time()
    try:
        logger.info("Assigning constitutional IDs")
        result = await fix_ids_internal(core_context, write=write)

        return ActionResult(
            action_id="fix.ids",
            ok=result.ok,
            data={
                "ids_assigned": result.data.get("ids_assigned", 0),
                "files_processed": result.data.get("files_processed", 0),
                "dry_run": not write,
            },
            duration_sec=result.duration_sec,
        )
    except Exception as e:
        logger.error("ID assignment failed: %s", e, exc_info=True)
        return ActionResult(
            action_id="fix.ids",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start,
        )


@register_action(
    action_id="fix.headers",
    description="Fix constitutional file headers",
    category=ActionCategory.FIX,
    policies=["constitutional_header_policy"],
    impact_level="safe",
)
# ID: c3d4e5f6-7890-abcd-ef12-34567890abcd
@atomic_action(
    action_id="fix.headers",
    intent="Atomic action for action_fix_headers",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 0595571a-7439-4362-b62a-b1c8aac18557
async def action_fix_headers(
    core_context: CoreContext, write: bool = False
) -> ActionResult:
    """
    Fix constitutional headers in all Python files.
    """
    start = time.time()
    try:
        logger.info("Fixing constitutional headers")
        result = await fix_headers_internal(core_context, write=write)

        return ActionResult(
            action_id="fix.headers",
            ok=result.ok,
            data={
                "headers_fixed": result.data.get("headers_fixed", 0),
                "files_processed": result.data.get("files_processed", 0),
                "dry_run": not write,
            },
            duration_sec=result.duration_sec,
        )
    except Exception as e:
        logger.error("Header fixing failed: %s", e, exc_info=True)
        return ActionResult(
            action_id="fix.headers",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start,
        )


@register_action(
    action_id="fix.docstrings",
    description="Fix missing or incomplete docstrings",
    category=ActionCategory.FIX,
    policies=["docstring_requirements"],
    impact_level="safe",
)
# ID: d4e5f678-90ab-cdef-1234-567890abcdef
@atomic_action(
    action_id="fix.docstrings",
    intent="Atomic action for action_fix_docstrings",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 96483c5c-ce10-41e4-8ba5-73f4a39988dc
async def action_fix_docstrings(
    core_context: CoreContext, write: bool = False
) -> ActionResult:
    """
    Fix missing or incomplete docstrings.
    """
    start = time.time()
    try:
        logger.info("Fixing docstrings")
        await fix_docstrings(core_context, write=write)

        return ActionResult(
            action_id="fix.docstrings",
            ok=True,
            data={
                "status": "completed",
                "dry_run": not write,
            },
            duration_sec=time.time() - start,
        )
    except Exception as e:
        logger.error("Docstring fixing failed: %s", e, exc_info=True)
        return ActionResult(
            action_id="fix.docstrings",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start,
        )


@register_action(
    action_id="fix.logging",
    description="Fix logging policy violations",
    category=ActionCategory.FIX,
    policies=["logging_policy"],
    impact_level="safe",
)
# ID: e5f67890-abcd-ef12-3456-7890abcdef12
@atomic_action(
    action_id="fix.logging",
    intent="Atomic action for action_fix_logging",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: ef8fe11c-fcff-49ea-a2ca-eaa9b0dbcc5e
async def action_fix_logging(
    core_context: CoreContext, write: bool = False
) -> ActionResult:
    """
    Fix logging policy violations (LOG-001, LOG-004).
    """
    start = time.time()
    try:
        logger.info("Fixing logging violations")
        # CONSTITUTIONAL FIX: Pass the governed file_handler
        fixer = LoggingFixer(
            settings.REPO_PATH,
            file_handler=core_context.file_handler,
            dry_run=not write,
        )
        result = fixer.fix_all()

        return ActionResult(
            action_id="fix.logging",
            ok=True,
            data={
                "fixes_applied": result["fixes_applied"],
                "files_modified": result["files_modified"],
                "dry_run": not write,
            },
            duration_sec=time.time() - start,
        )
    except Exception as e:
        logger.error("Logging fix failed: %s", e, exc_info=True)
        return ActionResult(
            action_id="fix.logging",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start,
        )


@register_action(
    action_id="fix.placeholders",
    description="Deterministically replace forbidden placeholders (FUTURE, none, pending)",
    category=ActionCategory.FIX,
    policies=["code_standards"],
    impact_level="moderate",
)
# ID: 7d8e9f0a-1b2c-3d4e-5f6g-7h8i9j0k1l2m
# ID: 4eadad7d-48b6-4799-9b52-646e4227f28e
@atomic_action(
    action_id="fix.placeholders",
    intent="Atomic action for action_fix_placeholders",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 5e5f8193-be98-4cbf-bef0-04e69d9c28ad
async def action_fix_placeholders(
    core_context: CoreContext, write: bool = False
) -> ActionResult:
    """
    Scans src/ and replaces forbidden placeholders with constitutional alternatives.
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

    # We import the string transformation helper from the command file
    # this avoids duplicating the complex line-editing code.
    from body.cli.commands.fix.atomic_actions import _fix_file_violations
    from body.cli.logic.atomic_actions_checker import AtomicActionsChecker

    start_time = time.time()
    root_path = core_context.git_service.repo_path

    checker = AtomicActionsChecker(root_path)
    result = checker.check_all()

    if not result.violations:
        return ActionResult(
            action_id="fix.atomic_actions",
            ok=True,
            data={"violations_fixed": 0, "files_modified": 0},
            duration_sec=time.time() - start_time,
        )

    # Group by file
    violations_by_file = {}
    for v in result.violations:
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
