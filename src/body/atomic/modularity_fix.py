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

ADR-140 D1/D7 (#769): fix.modularity is write-only. Target-file resolution,
layer/caller/symbol-inventory extraction, the modularity_analyze LLM call,
and split-plan acceptance gating (inventory + confidence) all moved to
will.agents.modularity_cognitive_delegate.ModularityCognitiveDelegate — the
Will-tier cognitive step of flow.fix_modularity. This action receives
resolved_file_path + plan_raw as required parameters and performs only the
deterministic mechanical split, decorator/logic conservation gates, and the
FileHandler write. MUST only be invoked via flow.fix_modularity; direct
invocation as a standalone action target is prohibited (no caller would
supply resolved_file_path/plan_raw).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from body.atomic.registry import ActionCategory, register_action
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.logger import getLogger


if TYPE_CHECKING:
    from pathlib import Path

    from body.infrastructure.storage.file_handler import FileHandler
    from shared.context import CoreContext

logger = getLogger(__name__)


_DECORATORS_TO_PRESERVE: frozenset[str] = frozenset(
    {"register_action", "atomic_action"}
)


def _decorator_simple_name(deco) -> str | None:
    """Return the trailing identifier of a decorator expression, or None.

    Handles ``@name``, ``@name(...)``, ``@mod.name``, ``@mod.name(...)``.
    """
    import ast as _ast

    if isinstance(deco, _ast.Name):
        return deco.id
    if isinstance(deco, _ast.Attribute):
        return deco.attr
    if isinstance(deco, _ast.Call):
        return _decorator_simple_name(deco.func)
    return None


def _collect_preserved_decorators(source: str) -> dict[str, set[str]]:
    """Map each decorated symbol → set of preserve-target decorator names.

    Walks the full AST so methods inside classes are covered alongside
    top-level functions and classes.
    """
    import ast as _ast

    try:
        tree = _ast.parse(source)
    except SyntaxError:
        return {}
    out: dict[str, set[str]] = {}
    for node in _ast.walk(tree):
        if not isinstance(
            node, _ast.FunctionDef | _ast.AsyncFunctionDef | _ast.ClassDef
        ):
            continue
        names = {
            n
            for d in node.decorator_list
            if (n := _decorator_simple_name(d)) is not None
        }
        targets = names & _DECORATORS_TO_PRESERVE
        if targets:
            out.setdefault(node.name, set()).update(targets)
    return out


def _invalidate_split_pycache(
    target: Path, file_handler: FileHandler, repo_root: Path
) -> list[Path]:
    """Remove stale .pyc artefacts left behind by a fix.modularity split.

    After step 7 writes the new package files and unlinks the original
    monolith, two regions can carry a .pyc that the daemon would otherwise
    serve on restart:

      - ``target.parent/__pycache__/<target.stem>.cpython-*.pyc`` —
        cached bytecode of the deleted monolith.
      - ``target.parent/<target.stem>`` (the new package directory) —
        nested ``__pycache__`` directories that may exist from a
        previous failed run.

    Mutations route through ``FileHandler.remove_file`` /
    ``FileHandler.remove_tree`` so the deletion is governed
    (architecture.governance_basics.logic_mutation_governed) and
    boundary-checked. Returns the absolute paths actually removed, for
    caller logging.

    See issue #212 / Failure 2 in CORE-ModularityLessons.md.
    """
    removed: list[Path] = []

    old_pycache = target.parent / "__pycache__"
    if old_pycache.is_dir():
        for stale in old_pycache.glob(f"{target.stem}.cpython-*.pyc"):
            try:
                rel = stale.relative_to(repo_root)
            except ValueError:
                continue
            file_handler.remove_file(str(rel))
            removed.append(stale)

    new_package_dir = target.parent / target.stem
    if new_package_dir.is_dir():
        for pycache_dir in new_package_dir.rglob("__pycache__"):
            if not pycache_dir.is_dir():
                continue
            try:
                rel = pycache_dir.relative_to(repo_root)
            except ValueError:
                continue
            file_handler.remove_tree(str(rel))
            removed.append(pycache_dir)

    return removed


def _check_decorator_conservation(
    original_source: str, produced_files: list[dict]
) -> list[str]:
    """Detect registration decorators present in *original_source* but missing
    from *produced_files*. Returns sorted ``"@deco on symbol"`` strings; empty
    list means conservation holds. ``__init__.py`` is skipped — re-exports
    don't carry definitions.
    """
    expected = _collect_preserved_decorators(original_source)
    if not expected:
        return []
    found: dict[str, set[str]] = {}
    for f in produced_files:
        path = f.get("path", "")
        if path.endswith("__init__.py"):
            continue
        for name, decos in _collect_preserved_decorators(f.get("content", "")).items():
            found.setdefault(name, set()).update(decos)
    missing: list[str] = []
    for sym, decos in expected.items():
        for d in decos:
            if d not in found.get(sym, set()):
                missing.append(f"@{d} on {sym}")
    return sorted(missing)


@register_action(
    action_id="fix.modularity",
    description="Mechanically split a file per a pre-validated LLM-produced plan",
    category=ActionCategory.FIX,
    policies=["rules/architecture/modularity"],
    remediates=[],  # ADR-095 D5: governor-invoked CLI tool only; no autonomous rule binding.
)
@atomic_action(
    action_id="fix.modularity",
    intent="Write-only: execute a pre-validated split plan mechanically. Logic Conservation Gate guards.",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 2e4e8a14-6495-4869-a047-43bb508d0d4a
async def action_fix_modularity(
    core_context: CoreContext,
    resolved_file_path: str,
    plan_raw: str,
    write: bool = False,
    **kwargs,
) -> ActionResult:
    """
    Mechanically execute a pre-validated split plan (ADR-140 D1/D7).

    resolved_file_path and plan_raw are produced by the preceding
    analyze.modularity_seam cognitive step (ModularityCognitiveDelegate),
    which already ran the modularity_analyze LLM call and gated the plan
    (inventory + confidence). This action performs one further defensive
    parse+validate pass on the received artifact, then the deterministic
    split, decorator/logic conservation gates, and the FileHandler write.
    No LLM calls. No prompt loading.
    """
    from body.atomic.modularity_splitter import ModularitySplitter
    from body.atomic.split_plan import SplitPlan, SplitPlanError
    from body.validators.logic_conservation_validator import LogicConservationValidator

    start = time.time()
    repo_root = core_context.git_service.repo_path

    target = repo_root / resolved_file_path
    if not target.exists():
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={"error": f"File not found: {resolved_file_path}"},
            duration_sec=time.time() - start,
        )

    rel_path = resolved_file_path
    original_content = target.read_text(encoding="utf-8")

    # One defensive parse+validate pass on the received artifact (ADR-140
    # D1) — the cognitive step already ran this same validation to decide
    # whether the plan was acceptable; this pass guards against the
    # artifact being malformed in transit, not against a bad LLM response.
    try:
        split_plan = SplitPlan.from_llm_json(plan_raw)
    except SplitPlanError as e:
        logger.error(
            "fix.modularity: could not parse plan_raw for %s: %s",
            rel_path,
            e,
        )
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={"error": f"plan validation failed: {e}", "file": rel_path},
            duration_sec=time.time() - start,
        )

    # Override structural fields — the action owns these, not the LLM.
    # LLM output routinely omits source_file and new_package_name;
    # trusting the LLM here causes ModularitySplitter to write to the
    # wrong location. target.stem is the authoritative package name
    # (enforced by validate() stem check).
    split_plan.source_file = rel_path
    split_plan.new_package_name = target.stem
    try:
        split_plan.validate()
    except SplitPlanError as e:
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={"error": f"plan re-validation failed: {e}", "file": rel_path},
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

    # 5a. Decorator Conservation Gate — fail fast before the LLM-backed
    # Logic Conservation Gate. Function bodies can be conserved while a
    # @register_action / @atomic_action decorator is silently dropped,
    # producing operationally broken output. See issue #211 / Failure 1
    # in CORE-ModularizationLessons.md.
    missing_decorators = _check_decorator_conservation(original_content, files)
    if missing_decorators:
        logger.error(
            "fix.modularity: decorator loss detected in %s: %s",
            rel_path,
            missing_decorators,
        )
        return ActionResult(
            action_id="fix.modularity",
            ok=False,
            data={
                "error": "decorator_loss_detected",
                "missing_decorators": missing_decorators,
                "file": rel_path,
            },
            duration_sec=time.time() - start,
        )

    # 6. Logic Conservation Gate
    proposed_map = {f["path"]: f["content"] for f in files}
    try:
        conservation_validator = LogicConservationValidator()  # type: ignore[abstract]
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

    # 7. Write files and delete original monolith
    if write:
        for file_info in files:
            core_context.file_handler.write_runtime_text(
                file_info["path"], file_info["content"]
            )
        logger.info(
            "fix.modularity: split complete — %d files written",
            len(files),
        )
        # Delete original monolith — the package __init__.py re-exports
        # all symbols so callers resolve without import-path changes.
        # Mirrors _execute_deterministic_split in the workflow path.
        if target.exists():
            core_context.file_handler.remove_file(rel_path)
            logger.info("fix.modularity: deleted original monolith %s", rel_path)

        # Issue #212 / Failure 2: invalidate stale .pyc so the daemon does
        # not serve the old monolith's bytecode (or stale bytecode under
        # the new package dir from previous failed runs) after restart.
        for invalidated in _invalidate_split_pycache(
            target, core_context.file_handler, repo_root
        ):
            try:
                logger.info(
                    "fix.modularity: invalidated stale bytecode %s",
                    invalidated.relative_to(repo_root),
                )
            except ValueError:
                logger.info(
                    "fix.modularity: invalidated stale bytecode %s", invalidated
                )
    else:
        logger.info(
            "fix.modularity: dry-run — would write %d files, delete %s",
            len(files),
            rel_path,
        )

    result_data = {
        "action": "split",
        "file": rel_path,
        "modules": len(split_plan.modules),
        "files_produced": [f["path"] for f in files],
        "files_count": len(files),
        "write": write,
    }
    if write:
        result_data["deleted_original"] = rel_path
    else:
        result_data["would_delete"] = rel_path

    return ActionResult(
        action_id="fix.modularity",
        ok=True,
        data=result_data,
        duration_sec=time.time() - start,
    )
