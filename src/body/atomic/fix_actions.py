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
    remediates=["style.formatter_required"],
)
@atomic_action(
    action_id="format.code",
    intent="Atomic action for action_format_code",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 5c3ede6c-23e1-4b92-8a00-7b2046eac121
async def action_format_code(
    file_path: str | None = None, write: bool = False, **kwargs
) -> ActionResult:
    """Format code using ruff format and ruff check."""
    start = time.time()
    from body.self_healing.code_style_service import format_code

    try:
        format_code(path=file_path, write=write)
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

    # ---- Sweep mode (legacy CLI) -------------------------------------------
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


_PATH_RESOLVER_PROPS: dict[str, str] = {"reports": "reports_dir", "logs": "logs_dir"}


def _is_target_constant(node: Any) -> bool:
    import ast as _ast

    return (
        isinstance(node, _ast.Constant)
        and isinstance(node.value, str)
        and node.value in _PATH_RESOLVER_PROPS
    )


def _has_target_descendant(node: Any) -> bool:
    """True if `node` or any descendant BinOp has a matching constant operand.

    Used to skip outer BinOps in chained path-division expressions where the
    runtime directory name appears as an intermediate operand.
    """
    import ast as _ast

    for sub in _ast.walk(node):
        if isinstance(sub, _ast.BinOp) and isinstance(sub.op, _ast.Div):
            if _is_target_constant(sub.left) or _is_target_constant(sub.right):
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
        if _is_target_constant(node.right):
            target, other = node.right, node.left
        elif _is_target_constant(node.left):
            target, other = node.left, node.right
        else:
            continue
        if _has_target_descendant(other):
            continue
        prop_name = _PATH_RESOLVER_PROPS[target.value]
        other_text = atok.get_text(other)
        replacement_text = f"PathResolver.from_repo({other_text}).{prop_name}"
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
