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

import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from body.atomic.registry import ActionCategory, register_action
from mind.governance.violation_report import ConstitutionalViolationError
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)

_RUNTIME_DIR_PATTERN = re.compile(
    r"""["'](?:reports|logs)/|/\s*["'](?:reports|logs)["']"""
)


def _error_data(exc: Exception, **extra: Any) -> dict[str, Any]:
    """Build ActionResult.data for an exception, preserving structure when available.

    ConstitutionalViolationError carries the full list[ViolationReport] that
    IntentGuard produced; we serialize it via to_dict() so rule_name, path,
    and source_policy survive the persistence hop into proposal.execution_results.
    Any other exception type degrades cleanly to the legacy flat {"error": str(e)}
    shape, so this helper is safe to adopt per-action without coordinated changes
    elsewhere.
    """
    if isinstance(exc, ConstitutionalViolationError):
        return {**exc.to_dict(), **extra}
    return {"error": str(exc), **extra}


@register_action(
    action_id="fix.format",
    description="Format code with ruff format and ruff check",
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
    remediates=["style.formatter_required", "workflow.ruff_format_check"],
)
@atomic_action(
    action_id="fix.format",
    intent="Atomic action for action_format_code",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 5c3ede6c-23e1-4b92-8a00-7b2046eac121
async def action_format_code(
    core_context: CoreContext | None = None,
    file_path: str | None = None,
    write: bool = False,
    **kwargs,
) -> ActionResult:
    """Format code using ruff format and ruff check.

    Runs ruff inside the execution context's repo_path so that when the
    action executes within a hermetic flow worktree (ADR-106) the format
    pass operates on the sandbox tree, not the real one (#638). A None
    context (defensive / non-executor path) falls back to the process cwd.
    """
    start = time.time()
    from body.self_healing.code_style_service import format_code

    cwd = (
        core_context.git_service.repo_path
        if core_context is not None and core_context.git_service is not None
        else None
    )
    try:
        format_code(path=file_path, write=write, cwd=cwd)
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
    remediates=["style.import_order", "style.no_unused_imports"],
)
@atomic_action(
    action_id="fix.imports",
    intent="Standardize Python import blocks using Ruff",
    impact=ActionImpact.WRITE_METADATA,
    policies=["atomic_actions"],
)
# ID: d5879178-fdfe-4d8b-b6a6-f887f8e9500b
async def action_fix_imports(
    core_context: CoreContext | None = None, write: bool = False, **kwargs
) -> ActionResult:
    """Sort and group Python imports according to constitutional style policy.

    Runs ruff inside the execution context's repo_path so an in-worktree
    flow execution (ADR-106) sorts imports in the sandbox tree, not the
    real one (#638). A None context falls back to the process cwd.
    """
    start = time.time()
    from shared.utils.subprocess_utils import run_poetry_command

    cwd = (
        core_context.git_service.repo_path
        if core_context is not None and core_context.git_service is not None
        else None
    )
    target_path = "src/"
    try:
        cmd = ["ruff", "check", target_path, "--select", "I"]
        if write:
            cmd.append("--fix")
        cmd.append("--exit-zero")

        run_poetry_command(f"Sorting imports in {target_path}", cmd, cwd=cwd)

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
    from body.self_healing.header_service import fix_headers_internal

    return await fix_headers_internal(core_context, write=write)


@register_action(
    action_id="fix.ids",
    description="Add missing ID tags to functions and classes",
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
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
    from body.self_healing.id_tagging_service import fix_ids_internal

    return await fix_ids_internal(core_context, write=write)


@register_action(
    action_id="fix.duplicate_ids",
    description="Resolve duplicate UUID collisions across source files",
    category=ActionCategory.FIX,
    policies=["rules/code/linkage"],
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
    from body.self_healing.duplicate_id_service import fix_duplicate_ids_internal

    return await fix_duplicate_ids_internal(core_context, write=write)


@register_action(
    action_id="fix.logging",
    description="Replace print statements with proper logging",
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
    remediates=[
        "logic.logging.standard_only",
        "architecture.channels.logic_no_terminal_rendering",
    ],
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
    from body.self_healing.logging_service import LoggingFixer

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
    remediates=["purity.no_todo_placeholders"],
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
    violations_by_file = {}
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


@register_action(
    action_id="fix.docstrings",
    description="Generate and inject missing docstrings using AI",
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
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
    core_context: CoreContext,
    file_path: str | None = None,
    write: bool = False,
    limit: int = 0,
    **kwargs,
) -> ActionResult:
    """Generate and inject missing docstrings using the Coder LLM role.

    Two invocation modes:

    1. Targeted (autonomous loop): caller supplies ``file_path`` in kwargs,
       e.g. via ProposalExecutor expanding ``actions[i].parameters.file_path``.
       Only symbols inside that file are evaluated. Mirrors the pattern
       used by ``action_format_code`` and ``action_fix_modularity``.
    2. Sweep (legacy CLI): no ``file_path`` supplied. The action walks every
       symbol in the knowledge graph, as before. ``limit`` caps the symbol
       count in sweep mode; 0 means unlimited and is ignored when
       ``file_path`` is set (matches body's fix_docstrings contract).

    Before this change the action discarded ``**kwargs``, so every targeted
    proposal silently degraded to a full-tree sweep — one proposal hammered
    Ollama for the whole codebase regardless of its declared scope.
    """
    start = time.time()
    from body.self_healing.docstring_service import fix_docstrings

    try:
        await fix_docstrings(
            context=core_context, write=write, limit=limit, file_path=file_path
        )
    except Exception as e:
        return ActionResult(
            action_id="fix.docstrings",
            ok=False,
            data={
                "error": str(e),
                "write": write,
                "file_path": file_path,
                "limit": limit,
            },
            duration_sec=time.time() - start,
        )
    return ActionResult(
        action_id="fix.docstrings",
        ok=True,
        data={"write": write, "file_path": file_path, "limit": limit},
        duration_sec=time.time() - start,
    )


@register_action(
    action_id="fix.purge_legacy_tags",
    description="Remove obsolete tag formats (e.g. legacy '# owner:', '# Tag:' lines)",
    category=ActionCategory.FIX,
    policies=["tag_hygiene"],
    remediates=["metadata.no_legacy_tags"],
)
@atomic_action(
    action_id="fix.purge_legacy_tags",
    intent="Remove legacy tag formats from source files",
    impact=ActionImpact.WRITE_METADATA,
    policies=["atomic_actions"],
)
# ID: 3c8d2f15-7e94-4a6b-b1c5-9d3f7e2a4b8d
async def action_fix_purge_legacy_tags(
    core_context: CoreContext,
    write: bool = False,
    **kwargs,
) -> ActionResult:
    """Wrap body.self_healing.purge_legacy_tags_service.purge_legacy_tags."""
    start = time.time()
    from body.self_healing.purge_legacy_tags_service import purge_legacy_tags

    try:
        removed = await purge_legacy_tags(core_context, dry_run=not write)
    except Exception as e:
        return ActionResult(
            action_id="fix.purge_legacy_tags",
            ok=False,
            data={"error": str(e), "write": write},
            duration_sec=time.time() - start,
        )
    return ActionResult(
        action_id="fix.purge_legacy_tags",
        ok=True,
        data={"removed": removed, "write": write},
        duration_sec=time.time() - start,
    )


@register_action(
    action_id="fix.capability_tagging",
    description="Tag untagged public capabilities using LLM-suggested names",
    category=ActionCategory.FIX,
    policies=["capability_tagging"],
    remediates=["symbols.capability_required"],
)
@atomic_action(
    action_id="fix.capability_tagging",
    intent="Tag untagged capabilities via LLM",
    impact=ActionImpact.WRITE_METADATA,
    policies=["atomic_actions"],
)
# ID: 7b3c8d51-9e2a-4f7b-a1e6-5c4d8b2f9a3e
async def action_fix_capability_tagging(
    core_context: CoreContext,
    write: bool = False,
    limit: int = 0,
    **kwargs,
) -> ActionResult:
    """Tag untagged capabilities via the will-layer naming agent.

    Wraps will.self_healing.capability_tagging_service.main_async. The
    body→will lazy import matches the precedent in
    proposal_lifecycle_actions.py — capability_tagging's CapabilityTaggerAgent
    legitimately depends on will/orchestration, so it stays in will/.
    """
    start = time.time()
    from shared.infrastructure.database.session_manager import get_session
    from will.self_healing.capability_tagging_service import main_async as tag

    try:
        await tag(
            session_factory=get_session,
            cognitive_service=core_context.cognitive_service,
            knowledge_service=core_context.knowledge_service,
            write=write,
            dry_run=not write,
            limit=limit,
        )
    except Exception as e:
        return ActionResult(
            action_id="fix.capability_tagging",
            ok=False,
            data={"error": str(e), "write": write, "limit": limit},
            duration_sec=time.time() - start,
        )
    return ActionResult(
        action_id="fix.capability_tagging",
        ok=True,
        data={"write": write, "limit": limit},
        duration_sec=time.time() - start,
    )


@register_action(
    action_id="fix.vulture_heal",
    description="Surgically remove Vulture-identified dead code using LLM analysis",
    category=ActionCategory.FIX,
    policies=["dead_code"],
    remediates=["workflow.dead_code_check"],
)
@atomic_action(
    action_id="fix.vulture_heal",
    intent="Remove dead code findings via LLM",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 5a2e9c4f-1b8d-43a7-92e6-7f3c1d4b8e5a
async def action_fix_vulture_heal(
    core_context: CoreContext,
    write: bool = False,
    **kwargs,
) -> ActionResult:
    """Surgical dead-code cleanup via the relocated body.self_healing.vulture_healer."""
    start = time.time()
    from body.self_healing.vulture_healer import heal_dead_code

    try:
        await heal_dead_code(
            context=core_context,
            file_handler=core_context.file_handler,
            repo_root=core_context.git_service.repo_path,
            write=write,
        )
    except Exception as e:
        return ActionResult(
            action_id="fix.vulture_heal",
            ok=False,
            data={"error": str(e), "write": write},
            duration_sec=time.time() - start,
        )
    return ActionResult(
        action_id="fix.vulture_heal",
        ok=True,
        data={"write": write},
        duration_sec=time.time() - start,
    )


@register_action(
    action_id="fix.settings_access",
    description="Refactor settings.* imports to dependency injection via CoreContext",
    category=ActionCategory.FIX,
    policies=["dependency_injection"],
    remediates=["architecture.body.no_settings_import"],
)
@atomic_action(
    action_id="fix.settings_access",
    intent="Refactor settings imports to DI via CoreContext",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 9e8d2c1f-3a6b-4d57-b9e2-1f4a8c5d3e0b
async def action_fix_settings_access(
    core_context: CoreContext,
    write: bool = False,
    layers: list[str] | None = None,
    **kwargs,
) -> ActionResult:
    """Refactor settings imports to dependency injection across given layers.

    Wraps body.maintenance.refactor_settings_access; translates the
    atomic-action convention (`write`) to the wrapped function's
    (`dry_run = not write`), passes repo_path from CoreContext, and
    surfaces the per-layer summary on data.results.
    """
    start = time.time()
    from body.maintenance.refactor_settings_access import refactor_settings_access

    try:
        results = await refactor_settings_access(
            repo_path=core_context.git_service.repo_path,
            layers=layers,
            dry_run=not write,
        )
    except Exception as e:
        return ActionResult(
            action_id="fix.settings_access",
            ok=False,
            data={"error": str(e), "write": write, "layers": layers},
            duration_sec=time.time() - start,
        )
    return ActionResult(
        action_id="fix.settings_access",
        ok=True,
        data={"results": results, "write": write, "layers": layers},
        duration_sec=time.time() - start,
    )


_PATH_RESOLVER_PROPS: dict[str, str] = {"reports": "reports_dir", "logs": "logs_dir"}


def _is_target_constant(node: Any) -> bool:
    import ast as _ast

    return (
        isinstance(node, _ast.Constant)
        and isinstance(node.value, str)
        and node.value in _PATH_RESOLVER_PROPS
    )


def _is_embedded_target_constant(node: Any) -> tuple[bool, str, str]:
    """Detect a Constant str whose value starts with ``reports/`` or ``logs/``.

    Returns ``(matched, prop_name, remainder)`` where ``prop_name`` is the
    matching PathResolver property (``reports_dir``/``logs_dir``) and
    ``remainder`` is the substring after the prefix-and-slash. ``remainder``
    may be empty for bare cases where only the prefix-and-slash is present.
    """
    import ast as _ast

    if not (isinstance(node, _ast.Constant) and isinstance(node.value, str)):
        return False, "", ""
    for prefix, prop_name in _PATH_RESOLVER_PROPS.items():
        head = f"{prefix}/"
        if node.value.startswith(head):
            return True, prop_name, node.value[len(head) :]
    return False, "", ""


def _has_target_descendant(node: Any) -> bool:
    """True if `node` or any descendant BinOp has a matching constant operand.

    Used to skip outer BinOps in chained path-division expressions where the
    runtime directory name appears as an intermediate operand. Detects both
    leaf-target forms and embedded-target forms (where the runtime directory
    name is the prefix of a longer Constant) so nested rewrites do not overlap.
    """
    import ast as _ast

    for sub in _ast.walk(node):
        if isinstance(sub, _ast.BinOp) and isinstance(sub.op, _ast.Div):
            if _is_target_constant(sub.left) or _is_target_constant(sub.right):
                return True
            if _is_embedded_target_constant(sub.right)[0]:
                return True
    return False


def _insert_path_resolver_import(source: str) -> str:
    """Insert ``from shared.path_resolver import PathResolver`` into the module.

    Idempotent — returns `source` unchanged if the import is already present.
    Inserts in alphabetically correct position within the existing first-party
    import block (CORE roots: api, body, cli, mind, shared, will). Falls back
    to appending after the last top-level Import/ImportFrom, or after a module
    docstring if no imports exist.
    """
    import ast as _ast

    import_line = "from shared.path_resolver import PathResolver"
    if import_line in source:
        return source

    try:
        import asttokens as _asttokens

        atok = _asttokens.ASTTokens(source, parse=True)
    except (SyntaxError, ImportError):
        return source
    tree = atok.tree

    new_module = "shared.path_resolver"
    first_party_roots = {"api", "body", "cli", "mind", "shared", "will"}

    # Absolute first-party ImportFrom siblings — same isort group as the new
    # import. Relative imports (level > 0) are excluded; they form a separate
    # group below first-party.
    siblings: list[Any] = []
    for node in tree.body:
        if (
            isinstance(node, _ast.ImportFrom)
            and node.module
            and node.level == 0
            and node.module.split(".")[0] in first_party_roots
        ):
            siblings.append(node)

    if siblings:
        insert_after = None
        insert_before = None
        for node in siblings:
            if node.module < new_module:
                insert_after = node
            else:
                insert_before = node
                break
        if insert_after is not None:
            _, end = atok.get_text_range(insert_after)
            return source[:end] + "\n" + import_line + source[end:]
        if insert_before is not None:
            start, _ = atok.get_text_range(insert_before)
            return source[:start] + import_line + "\n" + source[start:]

    # No first-party siblings — fall back to appending after the last import.
    last_import = None
    for node in tree.body:
        if isinstance(node, (_ast.Import, _ast.ImportFrom)):
            last_import = node

    if last_import is not None:
        _, end = atok.get_text_range(last_import)
        return source[:end] + "\n" + import_line + source[end:]

    # No imports: insert after module docstring if present, else at top.
    insert_at = 0
    if (
        tree.body
        and isinstance(tree.body[0], _ast.Expr)
        and isinstance(tree.body[0].value, _ast.Constant)
        and isinstance(tree.body[0].value.value, str)
    ):
        _, insert_at = atok.get_text_range(tree.body[0])

    return source[:insert_at] + "\n\n" + import_line + "\n" + source[insert_at:]


def _transform_path_resolver(source: str) -> tuple[str, int]:
    """Deterministic AST rewrite of hardcoded runtime dir literals.

    Walks the source for ``BinOp(op=Div)`` nodes where one operand is a
    ``Constant("reports")`` or ``Constant("logs")``. Each leaf match is
    replaced with ``PathResolver.from_repo(<other operand>).<dir>`` where
    ``<dir>`` is ``reports_dir`` or ``logs_dir`` respectively. Outer BinOps
    that contain a deeper match are skipped (leaf-only strategy) so source
    edits never overlap. Chained path-division expressions with a runtime
    directory name as an intermediate operand are handled by the leaf
    rewrite alone.

    Returns ``(new_source, replacement_count)``. If the source fails to
    parse, returns ``(source, 0)``.
    """
    import ast as _ast

    try:
        import asttokens as _asttokens

        atok = _asttokens.ASTTokens(source, parse=True)
    except (SyntaxError, ImportError):
        return source, 0
    tree = atok.tree

    replacements: list[tuple[int, int, str]] = []
    for node in _ast.walk(tree):
        if not (isinstance(node, _ast.BinOp) and isinstance(node.op, _ast.Div)):
            continue

        # Form 0 — leaf target: runtime directory name as a standalone Constant operand.
        if _is_target_constant(node.right):
            target, other = node.right, node.left
            prop_name = _PATH_RESOLVER_PROPS[target.value]
            remainder = ""
        elif _is_target_constant(node.left):
            target, other = node.left, node.right
            prop_name = _PATH_RESOLVER_PROPS[target.value]
            remainder = ""
        else:
            # Form 1 — embedded target: runtime directory name as the prefix of
            # a longer Constant on the right operand.
            matched, prop_name, remainder = _is_embedded_target_constant(node.right)
            if not matched:
                continue
            other = node.left

        if _has_target_descendant(other):
            continue

        other_text = atok.get_text(other)
        base = f"PathResolver.from_repo({other_text}).{prop_name}"
        replacement_text = f'{base} / "{remainder}"' if remainder else base
        start, end = atok.get_text_range(node)
        replacements.append((start, end, replacement_text))

    if not replacements:
        return source, 0

    replacements.sort(key=lambda r: r[0], reverse=True)
    new_source = source
    for start, end, text in replacements:
        new_source = new_source[:start] + text + new_source[end:]

    new_source = _insert_path_resolver_import(new_source)
    return new_source, len(replacements)


@register_action(
    action_id="fix.path_resolver",
    description="Rewrite hardcoded runtime directory literals to PathResolver accesses",
    category=ActionCategory.FIX,
    policies=["rules/architecture/path_access"],
    remediates=["architecture.path_access.no_hardcoded_runtime_dirs"],
)
@atomic_action(
    action_id="fix.path_resolver",
    intent="Rewrite hardcoded runtime directory path construction to PathResolver",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: f5c8e2a4-9b7d-4a1e-b0f3-6c2d4e8a9b15
async def action_fix_path_resolver(
    core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """Rewrite hardcoded runtime directory string literals to use PathResolver.

    Two invocation modes (mirrors action_fix_placeholders):

    1. Targeted (autonomous loop): caller supplies ``file_path`` in kwargs.
       The action operates on exactly that file. Bounded scope per
       invocation — matches the action's per-file impact contract.

    2. Sweep (CLI / debugging): no ``file_path`` supplied. The action walks
       every ``*.py`` under ``src/`` containing a runtime directory path literal
       that the rule's regex flags, and rewrites each.

    The rewrite is fully deterministic — no LLM call. ``_transform_path_resolver``
    parses the file with ``ast``/``asttokens`` and replaces leaf
    ``BinOp(op=Div)`` nodes whose operand is ``Constant("reports")`` or
    ``Constant("logs")`` with ``PathResolver.from_repo(<other>).<dir>``.
    The required ``from shared.path_resolver import PathResolver`` is
    inserted into the file's imports if not already present.

    Dry-run (``write=False``): returns a unified diff in ``data["diff"]``.
    """
    import difflib

    start = time.time()
    repo_root: Path = core_context.git_service.repo_path
    file_path = kwargs.get("file_path")

    def _build_diff(original: str, rewritten: str, rel: str) -> str:
        return "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                rewritten.splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
                n=3,
            )
        )

    # ---- Targeted mode ------------------------------------------------------
    if file_path:
        try:
            target_rel = str(file_path).lstrip("./")
            target_abs = (repo_root / target_rel).resolve()

            src_root = (repo_root / "src").resolve()
            try:
                target_abs.relative_to(src_root)
            except ValueError:
                return ActionResult(
                    action_id="fix.path_resolver",
                    ok=False,
                    data={
                        "error": f"Target outside src/ scope: {target_rel}",
                        "file_path": target_rel,
                    },
                    duration_sec=time.time() - start,
                )

            if not target_abs.is_file() or target_abs.suffix != ".py":
                return ActionResult(
                    action_id="fix.path_resolver",
                    ok=False,
                    data={
                        "error": f"Target is not a .py file: {target_rel}",
                        "file_path": target_rel,
                    },
                    duration_sec=time.time() - start,
                )

            original = target_abs.read_text(encoding="utf-8")

            if not _RUNTIME_DIR_PATTERN.search(original):
                return ActionResult(
                    action_id="fix.path_resolver",
                    ok=True,
                    data={
                        "files_affected": 0,
                        "written": False,
                        "file_path": target_rel,
                        "note": "no path_access literals matched",
                    },
                    duration_sec=time.time() - start,
                )

            rewritten, n_replacements = _transform_path_resolver(original)

            if n_replacements == 0 or rewritten == original:
                return ActionResult(
                    action_id="fix.path_resolver",
                    ok=True,
                    data={
                        "files_affected": 0,
                        "written": False,
                        "file_path": target_rel,
                        "note": (
                            "regex matched but no AST-level path-construction "
                            "BinOp/Div sites — likely string literal in a "
                            "non-path-construction context (e.g. exclude list, "
                            "docstring example)"
                        ),
                    },
                    duration_sec=time.time() - start,
                )

            if write:
                core_context.file_handler.write_runtime_text(target_rel, rewritten)

            return ActionResult(
                action_id="fix.path_resolver",
                ok=True,
                data={
                    "files_affected": 1,
                    "replacements": n_replacements,
                    "written": write,
                    "file_path": target_rel,
                    "diff": _build_diff(original, rewritten, target_rel),
                },
                duration_sec=time.time() - start,
            )
        except Exception as e:
            return ActionResult(
                action_id="fix.path_resolver",
                ok=False,
                data=_error_data(e, file_path=str(file_path)),
                duration_sec=time.time() - start,
            )

    # ---- Sweep mode ---------------------------------------------------------
    logger.warning(
        "fix.path_resolver invoked in sweep mode (no file_path). "
        "This mode is reserved for CLI callers; autonomous callers MUST "
        "supply file_path to stay within their declared impact scope."
    )

    files_modified = 0
    total_replacements = 0
    files_failed = 0
    files_skipped_no_match = 0

    try:
        src_dir = repo_root / "src"
        for py_file in src_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
                if not _RUNTIME_DIR_PATTERN.search(content):
                    files_skipped_no_match += 1
                    continue

                rewritten, n_replacements = _transform_path_resolver(content)
                if n_replacements == 0 or rewritten == content:
                    continue

                rel_path = str(py_file.relative_to(repo_root))
                if write:
                    core_context.file_handler.write_runtime_text(rel_path, rewritten)
                files_modified += 1
                total_replacements += n_replacements
            except Exception as e:
                logger.warning("fix.path_resolver: failed on %s: %s", py_file, e)
                files_failed += 1

        return ActionResult(
            action_id="fix.path_resolver",
            ok=files_failed == 0,
            data={
                "files_affected": files_modified,
                "replacements": total_replacements,
                "files_failed": files_failed,
                "files_skipped_no_match": files_skipped_no_match,
                "written": write,
                "mode": "sweep",
            },
            duration_sec=time.time() - start,
        )
    except Exception as e:
        return ActionResult(
            action_id="fix.path_resolver",
            ok=False,
            data=_error_data(e, mode="sweep"),
            duration_sec=time.time() - start,
        )
