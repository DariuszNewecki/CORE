# src/body/self_healing/handlers/id_assignment_handler.py
"""
ID assignment handler for audit remediation.

Pure-AST, deterministic handler. Inserts # ID: <uuid> comments above public
functions, methods, and classes that lack one in the file identified by the
audit finding. No LLM required.

Handler for check_id: linkage.assign_ids
"""

from __future__ import annotations

import ast
import time
import uuid
from pathlib import Path

from body.self_healing.remediation_models import FixResult
from shared.ast_utility import find_symbol_id_and_def_line
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from shared.models import AuditFinding


logger = getLogger(__name__)


def _is_public(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> bool:
    """Returns True if the symbol is public — no leading underscore, not a dunder."""
    is_dunder = node.name.startswith("__") and node.name.endswith("__")
    return not node.name.startswith("_") and not is_dunder


# ID: 3e8f1a2b-c4d5-4e6f-9a7b-8c2d0e1f3a5b
async def assign_missing_ids_handler(
    finding: AuditFinding,
    file_handler: FileHandler,
    repo_root: Path,
    write: bool,
) -> FixResult:
    """
    Insert # ID: <uuid> above every public function, method, and class in the
    file identified by the audit finding that currently lacks one.

    Algorithm:
        1. Parse the file with ast.parse.
        2. Walk the AST; for each public FunctionDef, AsyncFunctionDef, or
           ClassDef, call find_symbol_id_and_def_line to determine whether an
           ID tag already exists immediately above the def/class keyword
           (decorator-aware).
        3. Collect all missing-ID locations, sort descending by line number so
           that inserting a new line above an early symbol does not shift the
           line indices of later ones.
        4. Insert indentation-matched # ID: <uuid4> lines into the line list.
        5. Write the result via FileHandler (constitutional write gateway).

    Args:
        finding:      Audit finding from check_id=linkage.assign_ids.
                      finding.file_path must be relative to repo_root.
        file_handler: Constitutional write gateway.
        repo_root:    Repository root for path resolution.
        write:        If False, performs a dry-run and reports what would change.

    Returns:
        FixResult with ok=True on success or dry-run.
        changes_made keys:
            ids_inserted   — number of IDs written (write mode)
            would_insert   — number of IDs that would be written (dry-run)
            symbols        — names of affected symbols
            already_complete — True when no symbols are missing IDs
            duration_ms    — elapsed time
    """
    start_time = time.time()

    if not finding.file_path:
        logger.warning("Finding has no file_path, cannot fix: %s", finding.message)
        return FixResult(
            ok=False,
            error_message="No file path in finding",
            changes_made=None,
        )

    file_path = repo_root / finding.file_path
    if not file_path.exists():
        logger.error("File does not exist: %s", file_path)
        return FixResult(
            ok=False,
            error_message=f"File not found: {finding.file_path}",
            changes_made=None,
        )

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error("Failed to read file %s: %s", file_path, e)
        return FixResult(
            ok=False,
            error_message=f"Read failed: {e!s}",
            changes_made=None,
        )

    try:
        tree = ast.parse(content, filename=str(file_path))
    except SyntaxError as e:
        logger.error("Syntax error in %s — cannot assign IDs: %s", file_path.name, e)
        return FixResult(
            ok=False,
            error_message=f"Syntax error: {e!s}",
            changes_made=None,
        )

    source_lines = content.splitlines()

    # Collect all public symbols that are missing an ID tag.
    missing: list[dict] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not _is_public(node):
                continue
            id_result = find_symbol_id_and_def_line(node, source_lines)
            if not id_result.has_id:
                missing.append(
                    {
                        "line_number": id_result.definition_line_num,
                        "name": node.name,
                    }
                )

    if not missing:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info("No missing IDs in %s", finding.file_path)
        return FixResult(
            ok=True,
            error_message=None,
            changes_made={
                "ids_inserted": 0,
                "already_complete": True,
                "duration_ms": duration_ms,
            },
        )

    # Sort descending so inserting a line above an earlier symbol does not
    # shift the line indices of symbols that come later in the file.
    missing.sort(key=lambda x: x["line_number"], reverse=True)

    if not write:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "Dry-run: Would insert %d ID(s) in %s",
            len(missing),
            finding.file_path,
        )
        return FixResult(
            ok=True,
            error_message=None,
            changes_made={
                "dry_run": True,
                "would_insert": len(missing),
                "symbols": [f["name"] for f in missing],
                "duration_ms": duration_ms,
            },
        )

    lines = source_lines[:]
    for fix in missing:
        line_index = fix["line_number"] - 1
        original_line = lines[line_index]
        indentation = len(original_line) - len(original_line.lstrip(" "))
        tag_line = f"{' ' * indentation}# ID: {uuid.uuid4()}"
        lines.insert(line_index, tag_line)

    new_content = "\n".join(lines) + "\n"

    try:
        rel_path = str(file_path.relative_to(repo_root))
        file_handler.write_runtime_text(rel_path, new_content)
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "Inserted %d ID(s) in %s (%d ms)",
            len(missing),
            finding.file_path,
            duration_ms,
        )
        return FixResult(
            ok=True,
            error_message=None,
            changes_made={
                "ids_inserted": len(missing),
                "symbols": [f["name"] for f in missing],
                "duration_ms": duration_ms,
                "file_path": rel_path,
            },
        )
    except Exception as e:
        logger.error("Failed to write via FileHandler: %s", e)
        return FixResult(
            ok=False,
            error_message=f"FileHandler write failed: {e!s}",
            changes_made=None,
        )
