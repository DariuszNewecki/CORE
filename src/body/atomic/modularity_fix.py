# src/body/atomic/modularity_fix.py
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


def _extract_class_methods_context(source: str) -> str:
    """
    Detect the dominant class in a file and extract method/assignment inventory.

    A class is dominant if it has the most methods among all top-level classes
    and that count is at least 3. This mirrors the heuristic used by
    ModularitySplitter (dominant = largest class when method count exceeds
    half of plan symbols), adapted for pre-plan context where we use a
    fixed threshold of 3 methods instead.

    Returns a formatted string listing the class name, all method names,
    and class-level assignments, or a sentinel string if no dominant class
    is found.

    This gives the LLM a precise symbol list so it only needs to reason
    about grouping — not discover symbols by reading the full file.
    """
    import ast as _ast

    try:
        tree = _ast.parse(source)
        class_defs = [
            n for n in _ast.iter_child_nodes(tree) if isinstance(n, _ast.ClassDef)
        ]
        if not class_defs:
            return "(not a single-class file)"

        # Find the class with the most methods
        best = None
        best_count = 0
        for cls in class_defs:
            methods = [
                n
                for n in cls.body
                if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef))
            ]
            if len(methods) > best_count:
                best_count = len(methods)
                best = cls

        if best is None or best_count < 3:
            return "(not a single-class file)"

        dominant = best
        method_names = [
            n.name
            for n in dominant.body
            if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef))
        ]

        # Collect class-level assignments (Assign and AnnAssign directly in class body)
        assignment_names = []
        for n in dominant.body:
            if isinstance(n, _ast.AnnAssign) and isinstance(n.target, _ast.Name):
                assignment_names.append(n.target.id)
            elif isinstance(n, _ast.Assign):
                for target in n.targets:
                    if isinstance(target, _ast.Name):
                        assignment_names.append(target.id)

        result = (
            f"Dominant class: {dominant.name}\n"
            f"Methods ({len(method_names)}):\n"
            + "\n".join(f"  - {m}" for m in method_names)
        )

        if assignment_names:
            result += (
                f"\nClass-level assignments ({len(assignment_names)}):\n"
                + "\n".join(f"  - {a}" for a in assignment_names)
            )

        return result
    except Exception:
        pass
    return "(not a single-class file)"


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
    from body.atomic.modularity_splitter import ModularitySplitter
    from body.atomic.split_plan import SplitPlan, SplitPlanError
    from body.validators.logic_conservation_validator import LogicConservationValidator
    from shared.models.prompt_model import PromptModel

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

    # 2. Extract class method inventory deterministically from AST.
    # For single-dominant-class files this gives the LLM a precise symbol
    # list so it only needs to reason about grouping, not discover symbols.
    class_methods_context = _extract_class_methods_context(original_content)

    # 3. Phase 1 — find the seam via LLM
    try:
        analyze_model = PromptModel.load("modularity_analyze")
        analyze_client = await core_context.cognitive_service.aget_client_for_role(
            analyze_model.manifest.role
        )
        plan_raw = await analyze_model.invoke(
            analyze_client,
            {
                "file_path": rel_path,
                "layer": layer,
                "violations": "architecture.max_file_size, modularity.refactor_score_threshold",
                "line_count": str(line_count),
                "content": original_content,
                "callers": "\n".join(callers) if callers else "(none)",
                "class_methods": class_methods_context,
            },
        )
    except Exception as e:
        logger.error("fix.modularity: analyze phase failed: %s", e)
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={"error": f"analyze phase failed: {e}", "file": rel_path},
            duration_sec=time.time() - start,
        )

    # 4. Parse LLM response into a validated SplitPlan
    try:
        split_plan = SplitPlan.from_llm_json(plan_raw)
    except SplitPlanError as e:
        logger.error(
            "fix.modularity: could not parse analyze response: %s\nRaw: %s",
            e,
            plan_raw[:500] if plan_raw else "(empty)",
        )
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={"error": f"plan validation failed: {e}", "file": rel_path},
            duration_sec=time.time() - start,
        )

    logger.info(
        "fix.modularity: %s — split plan validated (%d modules), proceeding",
        rel_path,
        len(split_plan.modules),
    )

    # 5. Phase 2 — deterministic split via ModularitySplitter
    logger.info(
        "fix.modularity: executing mechanical split of %s into %d modules",
        rel_path,
        len(split_plan.modules),
    )

    try:
        splitter = ModularitySplitter()
        split_result = splitter.split(source_path=target, plan=split_plan)
        files = [
            {"path": str(p.relative_to(repo_root)), "content": content}
            for p, content in split_result.files
        ]
    except SplitPlanError as e:
        logger.error("fix.modularity: split failed — %s", e)
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={"error": f"split failed: {e}", "file": rel_path},
            duration_sec=time.time() - start,
        )

    if not files:
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={"error": "split produced no files", "file": rel_path},
            duration_sec=time.time() - start,
        )

    # 6. Logic Conservation Gate
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

    # 7. Write files
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
            "modules": len(split_plan.modules),
            "files_produced": [f["path"] for f in files],
            "files_count": len(files),
            "write": write,
        },
        duration_sec=time.time() - start,
    )
