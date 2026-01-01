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
from shared.action_types import ActionResult
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
async def action_fix_ids(
    core_context: CoreContext, write: bool = False
) -> ActionResult:
    """
    Assign unique IDs to all functions and classes.
    """
    start = time.time()
    try:
        logger.info("Assigning constitutional IDs")
        # FIXED: Pass core_context and await
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
async def action_fix_headers(
    core_context: CoreContext, write: bool = False
) -> ActionResult:
    """
    Fix constitutional headers in all Python files.
    """
    start = time.time()
    try:
        logger.info("Fixing constitutional headers")
        # FIXED: Pass core_context and await
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
async def action_fix_logging(write: bool = False) -> ActionResult:
    """
    Fix logging policy violations (LOG-001, LOG-004).
    """
    start = time.time()
    try:
        logger.info("Fixing logging violations")
        fixer = LoggingFixer(settings.REPO_PATH, dry_run=not write)
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
async def action_fix_placeholders(
    core_context: CoreContext, write: bool = False
) -> ActionResult:
    """
    Scans src/ and replaces forbidden placeholders with constitutional alternatives.
    """
    start = time.time()
    files_modified = 0

    try:
        src_dir = core_context.git_service.repo_path / "src"
        for py_file in src_dir.rglob("*.py"):
            original = py_file.read_text(encoding="utf-8")
            fixed = fix_placeholders_in_content(original)

            if fixed != original:
                if write:
                    py_file.write_text(fixed, encoding="utf-8")
                    logger.info("Fixed placeholders in %s", py_file.name)
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
