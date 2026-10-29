# src/body/self_healing/header_service.py

"""
fix.headers — enforces the constitutional file header law.
All mutations go through the canonical ActionExecutor Gateway.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from body.atomic.executor import ActionExecutor
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action

# REFACTORED: Removed direct settings import
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: 4828affd-f7da-4995-9493-7037211b4144
async def _run_header_fix_cycle(
    context: CoreContext, dry_run: bool, all_py_files: list[str]
) -> dict[str, Any]:
    """
    Enforce the src/**/*.py path-header invariant.

    Invariant: line 1 MUST be exactly '# <repo-relative-path>' for each src/**/*.py file.
    This exists to keep file metadata deterministic and machine-verifiable.
    """
    logger.info("🔍 Scanning %d files for header compliance...", len(all_py_files))

    executor = ActionExecutor(context)
    write_mode = not dry_run
    files_changed = 0
    files_created = 0
    changed_paths: list[str] = []

    def _enforce_line1_path_header(
        content: str, expected_header: str
    ) -> tuple[str, bool]:
        """
        Return (new_content, did_change) enforcing the path-header invariant:
        - Empty file            -> insert header
        - Line 1 == correct     -> no change
        - Line 1 is a # src/.. -> wrong path, replace line 1
        - Anything else         -> prepend header, leave file content intact
        """
        if content == "":
            return expected_header + "\n", True

        lines = content.splitlines(keepends=True)
        first_line_text = lines[0].rstrip("\r\n")

        if first_line_text == expected_header:
            return content, False

        if first_line_text.startswith("# src/"):
            # Wrong path header — replace only line 1
            lines[0] = expected_header + "\n"
            return "".join(lines), True

        # Not a path header (could be # ID:, docstring, code, anything)
        # Prepend and leave everything else intact
        return expected_header + "\n" + content, True

    for i, file_path_str in enumerate(all_py_files, 1):
        if i % 50 == 0:
            logger.debug("Header analysis progress: %d/%d", i, len(all_py_files))

        file_path = context.git_service.repo_path / file_path_str
        try:
            original_content = file_path.read_text(encoding="utf-8")
            expected_header = f"# {Path(file_path_str).as_posix()}"
            corrected_code, changed = _enforce_line1_path_header(
                original_content, expected_header
            )
            if not changed:
                continue

            result = await executor.execute(
                action_id="file.edit",
                write=write_mode,
                file_path=file_path_str,
                code=corrected_code,
            )
            if result.ok:
                files_changed += 1
                changed_paths.append(file_path_str)
                if original_content == "":
                    files_created += 1
            else:
                logger.warning("   -> [BLOCKED] %s", file_path_str)

        except Exception as e:
            logger.warning("Could not process %s: %s", file_path_str, e)

    if files_changed == 0:
        logger.info("✅ All file headers are constitutionally compliant.")
    else:
        mode_label = "Fixed" if write_mode else "Proposed fixes for"
        logger.info(
            "🏁 Header fix cycle complete. %s %d file(s).", mode_label, files_changed
        )

        if write_mode:
            logger.info("🔄 Rebuilding Knowledge Graph to reflect metadata changes...")
            await executor.execute(action_id="sync.db", write=True)
            logger.info("✅ Knowledge Graph successfully updated.")

    return {
        "total_files_scanned": len(all_py_files),
        "files_changed": files_changed,
        "files_unchanged": len(all_py_files) - files_changed,
        "files_created": files_created,
        "changed_file_paths": changed_paths,
    }


@atomic_action(
    action_id="fix.headers",
    intent="Ensure all Python files have constitutionally compliant headers",
    impact=ActionImpact.WRITE_METADATA,
    policies=["file_headers"],
    category="fixers",
)
# ID: 936e32e6-18a3-4b7c-a0f2-06cc8ca654f7
async def fix_headers_internal(
    context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """
    Core orchestrator for fix.headers — moved from cli/commands/fix/code_style.py
    under ADR-050. Walks src/, dispatches to _run_header_fix_cycle.
    """
    start_time = time.time()
    repo_root = context.git_service.repo_path
    try:
        src_dir = repo_root / "src"
        all_py_files = [
            p.relative_to(repo_root).as_posix() for p in src_dir.rglob("*.py")
        ]
        summary = await _run_header_fix_cycle(
            context, dry_run=not write, all_py_files=all_py_files
        )
        return ActionResult(
            action_id="fix.headers",
            ok=True,
            data={
                "total_files_scanned": summary["total_files_scanned"],
                "files_changed": summary["files_changed"],
                "files_unchanged": summary["files_unchanged"],
                "files_created": summary["files_created"],
                "changed_file_paths": summary["changed_file_paths"],
                "files_scanned": summary["total_files_scanned"],
                "violations_found": summary["files_changed"],
                "fixed_count": summary["files_changed"] if write else 0,
                "dry_run": not write,
                "mode": "write" if write else "dry-run",
            },
            duration_sec=time.time() - start_time,
            impact=ActionImpact.WRITE_METADATA if write else ActionImpact.READ_ONLY,
        )
    except Exception as e:
        return ActionResult(
            action_id="fix.headers",
            ok=False,
            data={"error": str(e), "error_type": type(e).__name__},
            duration_sec=time.time() - start_time,
            logs=[f"Exception during header fix: {e}"],
        )
