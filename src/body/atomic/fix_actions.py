# src/body/atomic/fix_actions.py

"""
Atomic Fix Actions - Code Remediation

Each action does ONE thing and returns ActionResult.
Actions are composable, auditable, and constitutionally governed.

Constitutional Alignment:
- Boundary: Uses CoreContext for repo_path (no direct settings access)
- Circularity Fix: Feature-level imports are performed inside functions.
- Remediation: Each action declares which audit check_ids it fixes via remediates=[].
  ViolationRemediatorWorker uses this to close the autonomous audit loop.
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
    remediates=["style.formatter_required"],
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
    from body.self_healing.code_style_service import format_code

    try:
        format_code(write=write)
    except Exception as e:
        return ActionResult(
            action_id="fix.format",
            ok=False,
            data={"error": str(e), "write": write},
            duration_sec=time.time() - start,
        )
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
    remediates=["style.import_order", "style.no_unused_imports"],
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
    action_id="fix.headers",
    description="Fix file headers to match constitutional standards",
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
    impact_level="safe",
    remediates=["layout.src_module_header"],
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
    from cli.commands.fix.code_style import fix_headers_internal

    return await fix_headers_internal(core_context, write=write)


@register_action(
    action_id="fix.ids",
    description="Add missing ID tags to functions and classes",
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
    impact_level="safe",
    remediates=["purity.stable_id_anchor", "linkage.assign_ids"],
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
    from cli.commands.fix.metadata import fix_ids_internal

    return await fix_ids_internal(core_context, write=write)


@register_action(
    action_id="fix.duplicate_ids",
    description="Resolve duplicate UUID collisions across source files",
    category=ActionCategory.FIX,
    policies=["rules/code/linkage"],
    impact_level="moderate",
    remediates=["linkage.duplicate_ids"],
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
    from cli.commands.fix.metadata import fix_duplicate_ids_internal

    return await fix_duplicate_ids_internal(core_context, write=write)


@register_action(
    action_id="fix.logging",
    description="Replace print statements with proper logging",
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
    impact_level="safe",
    remediates=["logic.logging.standard_only"],
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
    from cli.commands.fix_logging import LoggingFixer

    if core_context.file_handler is None:
        return ActionResult(
            action_id="fix.logging",
            ok=False,
            data={"error": "file_handler not initialized"},
            duration_sec=time.time() - start,
        )
    fixer = LoggingFixer(
        repo_root=core_context.git_service.repo_path,
        file_handler=core_context.file_handler,
        dry_run=not write,
    )
    try:
        result = fixer.fix_all()
    except Exception as e:
        return ActionResult(
            action_id="fix.logging",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start,
        )
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
    remediates=["caps.no_placeholder_text"],
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
    from body.self_healing.placeholder_fixer_service import (
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
    remediates=["architecture.atomic_actions.must_return_action_result"],
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
    from body.evaluators.atomic_actions_evaluator import (
        AtomicActionsEvaluator,
        AtomicActionViolation,
    )
    from cli.commands.fix.atomic_actions import _fix_file_violations

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

    violations_by_file = {}
    for v in violations:
        violations_by_file.setdefault(v.file_path, []).append(v)

    fixes_applied = 0
    files_modified = 0
    files_failed = 0

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


@register_action(
    action_id="fix.docstrings",
    description="Generate and inject missing docstrings using AI",
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
    impact_level="moderate",
    remediates=["purity.docstrings.required"],
)
@atomic_action(
    action_id="fix.docstrings",
    intent="Autonomously generate missing docstrings via Coder LLM role",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: a3f91c7d-5e2b-4d8a-b6f0-c1e2d3f4a5b7
async def action_fix_docstrings(
    core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """Generate and inject missing docstrings using the Coder LLM role."""
    start = time.time()
    from body.self_healing.docstring_service import fix_docstrings

    try:
        await fix_docstrings(context=core_context, write=write)
    except Exception as e:
        return ActionResult(
            action_id="fix.docstrings",
            ok=False,
            data={"error": str(e), "write": write},
            duration_sec=time.time() - start,
        )
    return ActionResult(
        action_id="fix.docstrings",
        ok=True,
        data={"write": write},
        duration_sec=time.time() - start,
    )


def _find_worst_modularity_violator(repo_root):
    """Find the src/ Python file with the most lines. Excludes __init__.py and tests."""
    from pathlib import Path

    skip_dirs = {"tests", "__pycache__", ".venv", "venv", ".git", "work", "var"}
    src_root = repo_root / "src"
    if not src_root.exists():
        return None

    worst: tuple[int, Path] | None = None
    for py_file in src_root.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        if any(part in py_file.parts for part in skip_dirs):
            continue
        try:
            line_count = len(py_file.read_text(encoding="utf-8").splitlines())
            if line_count >= 400:
                if worst is None or line_count > worst[0]:
                    worst = (line_count, py_file)
        except Exception:
            continue
    return worst[1] if worst else None


def _detect_layer_from_path(path, repo_root) -> str:
    """Detect architectural layer from file path."""
    rel = str(path.relative_to(repo_root))
    if rel.startswith("src/mind"):
        return "mind"
    if rel.startswith("src/body"):
        return "body"
    if rel.startswith("src/will"):
        return "will"
    if rel.startswith("src/shared"):
        return "shared"
    return "unknown"


def _find_callers(target_path, repo_root) -> list[str]:
    """Find files in src/ that import from the target module."""
    import ast

    target_module = (
        str(target_path.relative_to(repo_root)).replace("/", ".").removesuffix(".py")
    )
    if target_module.startswith("src."):
        target_module = target_module[4:]

    callers = []
    src_root = repo_root / "src"
    for py_file in src_root.rglob("*.py"):
        if py_file == target_path:
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import | ast.ImportFrom):
                    if isinstance(node, ast.ImportFrom) and node.module:
                        if node.module == target_module or node.module.startswith(
                            target_module + "."
                        ):
                            callers.append(str(py_file.relative_to(repo_root)))
                            break
        except Exception:
            continue
    return callers


@register_action(
    action_id="fix.modularity",
    description="Split a file that violates modularity rules using two-phase LLM analysis",
    category=ActionCategory.FIX,
    policies=["rules/architecture/modularity"],
    impact_level="moderate",
    remediates=[
        "architecture.max_file_size",
        "modularity.refactor_score_threshold",
        "modularity.single_responsibility",
        "modularity.import_coupling",
        "modularity.semantic_cohesion",
    ],
)
@atomic_action(
    action_id="fix.modularity",
    intent="Two-phase split: Architect finds the seam, RefactoringArchitect executes. Logic Conservation Gate guards.",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 2e4e8a14-6495-4869-a047-43bb508d0d4a
async def action_fix_modularity(
    core_context: CoreContext,
    write: bool = False,
    file_path: str | None = None,
    **kwargs,
) -> ActionResult:
    """
    Split a modularity-violating file using two-phase LLM analysis.

    Phase 1 (modularity_analyze): Architect finds the natural seam and
    assigns confidence. Low/medium confidence defers to human session.

    Phase 2 (modularity_split): RefactoringArchitect executes the approved
    plan mechanically. Logic Conservation Gate validates before any write.
    """
    import json

    from body.validators.logic_conservation_validator import LogicConservationValidator
    from shared.ai.prompt_model import PromptModel

    start = time.time()
    repo_root = core_context.git_service.repo_path

    # 1. Find target file
    if file_path:
        target = repo_root / file_path
        if not target.exists():
            return ActionResult(
                action_id="fix.modularity",
                ok=False,
                data={"error": f"File not found: {file_path}"},
                duration_sec=time.time() - start,
            )
    else:
        target = _find_worst_modularity_violator(repo_root)
        if target is None:
            return ActionResult(
                action_id="fix.modularity",
                ok=True,
                data={"message": "No modularity violations found"},
                duration_sec=time.time() - start,
            )

    rel_path = str(target.relative_to(repo_root))
    original_content = target.read_text(encoding="utf-8")
    line_count = len(original_content.splitlines())
    layer = _detect_layer_from_path(target, repo_root)
    callers = _find_callers(target, repo_root)

    logger.info(
        "fix.modularity: analyzing %s (%d lines, layer=%s, callers=%d)",
        rel_path,
        line_count,
        layer,
        len(callers),
    )

    # 2. Phase 1 — find the seam
    try:
        analyze_model = PromptModel.load("modularity_analyze")
        analyze_client = await core_context.cognitive_service.aget_client_for_role(
            analyze_model.manifest.role
        )
        plan_raw = await analyze_model.invoke(
            context={
                "file_path": rel_path,
                "layer": layer,
                "violations": "architecture.max_file_size, modularity.refactor_score_threshold",
                "line_count": str(line_count),
                "content": original_content,
                "callers": "\n".join(callers) if callers else "(none)",
            },
            client=analyze_client,
            user_id="fix_modularity_action",
        )
    except Exception as e:
        logger.error("fix.modularity: analyze phase failed: %s", e)
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={"error": f"analyze phase failed: {e}", "file": rel_path},
            duration_sec=time.time() - start,
        )

    try:
        plan = json.loads(plan_raw)
    except Exception as e:
        logger.error("fix.modularity: could not parse analyze response: %s", e)
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={"error": "analyze response not valid JSON", "file": rel_path},
            duration_sec=time.time() - start,
        )

    # 3. Evaluate confidence
    can_split = plan.get("can_split", False)
    confidence = plan.get("confidence", "low")
    reason = plan.get("reason", "")

    if not can_split:
        logger.info(
            "fix.modularity: %s is cohesive, no split needed — %s",
            rel_path,
            reason,
        )
        return ActionResult(
            action_id="fix.modularity",
            ok=True,
            data={"action": "no_split", "file": rel_path, "reason": reason},
            duration_sec=time.time() - start,
        )

    if confidence in ("low", "medium"):
        logger.info(
            "fix.modularity: %s confidence=%s — deferring to human session",
            rel_path,
            confidence,
        )
        return ActionResult(
            action_id="fix.modularity",
            ok=True,
            data={
                "action": "deferred",
                "file": rel_path,
                "confidence": confidence,
                "reason": reason,
                "plan": plan,
            },
            duration_sec=time.time() - start,
        )

    logger.info(
        "fix.modularity: %s confidence=high — proceeding to split phase",
        rel_path,
    )

    # 4. Phase 2 — execute the split
    try:
        split_model = PromptModel.load("modularity_split")
        split_client = await core_context.cognitive_service.aget_client_for_role(
            split_model.manifest.role
        )
        split_raw = await split_model.invoke(
            context={
                "file_path": rel_path,
                "layer": layer,
                "content": original_content,
                "plan": plan_raw,
            },
            client=split_client,
            user_id="fix_modularity_action",
        )
    except Exception as e:
        logger.error("fix.modularity: split phase failed: %s", e)
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={"error": f"split phase failed: {e}", "file": rel_path},
            duration_sec=time.time() - start,
        )

    try:
        split_result = json.loads(split_raw)
        files = split_result.get("files", [])
    except Exception as e:
        logger.error("fix.modularity: could not parse split response: %s", e)
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={"error": "split response not valid JSON", "file": rel_path},
            duration_sec=time.time() - start,
        )

    if not files:
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={"error": "split produced no files", "file": rel_path},
            duration_sec=time.time() - start,
        )

    # 5. Logic Conservation Gate
    proposed_map = {f["path"]: f["content"] for f in files}
    try:
        conservation_validator = LogicConservationValidator()
        verdict = await conservation_validator.evaluate(
            original_code=original_content,
            proposed_map=proposed_map,
            deletions_authorized=False,
        )
    except Exception as e:
        logger.error("fix.modularity: Logic Conservation Gate failed: %s", e)
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={"error": f"conservation gate error: {e}", "file": rel_path},
            duration_sec=time.time() - start,
        )

    if not verdict.ok:
        ratio = verdict.data.get("ratio", 0.0)
        logger.error(
            "fix.modularity: logic evaporation in %s (ratio=%.2f) — aborting",
            rel_path,
            ratio,
        )
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={
                "error": "logic_evaporation",
                "ratio": ratio,
                "file": rel_path,
            },
            duration_sec=time.time() - start,
        )

    # 6. Write files
    if write:
        for file_info in files:
            core_context.file_handler.write_runtime_text(
                file_info["path"], file_info["content"]
            )
        logger.info(
            "fix.modularity: split complete — %d files written",
            len(files),
        )
    else:
        logger.info(
            "fix.modularity: dry-run — would write %d files",
            len(files),
        )

    return ActionResult(
        action_id="fix.modularity",
        ok=True,
        data={
            "action": "split",
            "file": rel_path,
            "confidence": confidence,
            "files_produced": [f["path"] for f in files],
            "files_count": len(files),
            "write": write,
        },
        duration_sec=time.time() - start,
    )
