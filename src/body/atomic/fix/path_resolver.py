# src/body/atomic/fix/path_resolver.py

"""fix.path_resolver — rewrite hardcoded runtime directory literals to PathResolver.

Split from body/atomic/fix_actions.py (one action per module, #806).
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

from body.atomic.fix._shared import _error_data
from body.atomic.path_resolver_rewriter import _transform_path_resolver
from body.atomic.registry import ActionCategory, register_action
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)

_RUNTIME_DIR_PATTERN = re.compile(
    r"""["'](?:reports|logs|prompts|exports|workflows|build|context)/"""
    r"""|/\s*["'](?:reports|logs|prompts|exports|workflows|build|context)["']"""
)


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
    ``BinOp(op=Div)`` nodes whose operand matches a key in ``_PATH_RESOLVER_PROPS``
    (reports, logs, prompts, exports, workflows, build, context) with
    ``PathResolver.from_repo(<other>).<dir_property>``.
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
