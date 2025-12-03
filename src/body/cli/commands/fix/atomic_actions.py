# src/body/cli/commands/fix/atomic_actions.py

"""
Fix atomic actions pattern violations.

This module provides functionality to automatically fix violations detected by
the atomic-actions checker, including missing decorators, return types, and metadata.
"""

from __future__ import annotations

from pathlib import Path

from shared.cli_types import CommandResult
from shared.logger import getLogger

from body.cli.logic.atomic_actions_checker import AtomicActionsChecker

logger = getLogger(__name__)


# ID: 4f8e9d7c-6a5b-3e2f-9c8d-7b6e9f4a8c7e
def fix_atomic_actions_internal(
    root_path: Path,
    write: bool = False,
) -> CommandResult:
    """
    Fix atomic actions pattern violations.

    Args:
        root_path: Root directory to scan
        write: If True, apply fixes; if False, dry-run mode

    Returns:
        CommandResult with fix statistics
    """
    checker = AtomicActionsChecker(root_path)
    result = checker.check_all()

    if not result.violations:
        return CommandResult(
            name="fix.atomic_actions",
            ok=True,
            data={"files_checked": result.total_actions, "violations_fixed": 0},
        )

    # Group violations by file
    violations_by_file: dict[Path, list] = {}
    for violation in result.violations:
        if violation.file_path not in violations_by_file:
            violations_by_file[violation.file_path] = []
        violations_by_file[violation.file_path].append(violation)

    fixes_applied = 0
    files_modified = 0

    for file_path, file_violations in violations_by_file.items():
        try:
            with open(file_path, encoding="utf-8") as f:
                source = f.read()

            modified_source = _fix_file_violations(source, file_violations, file_path)

            if modified_source != source:
                if write:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(modified_source)
                    files_modified += 1
                    logger.info(f"Fixed {file_path}")
                else:
                    print(f"\n[DRY RUN] Would modify {file_path}:")
                    _show_preview(file_violations)

                fixes_applied += len(file_violations)

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            continue

    mode = "Applied" if write else "Would apply"
    message = f"{mode} {fixes_applied} fixes to {files_modified} files"

    return CommandResult(
        name="fix.atomic_actions",
        ok=True,
        data={
            "files_modified": files_modified,
            "violations_fixed": fixes_applied,
            "dry_run": not write,
        },
    )


def _fix_file_violations(source: str, violations: list, file_path: Path) -> str:
    """
    Fix all violations in a single file.

    Args:
        source: Original source code
        violations: List of violations to fix
        file_path: Path to file being fixed

    Returns:
        Modified source code
    """
    # Apply fixes line by line (simpler than AST for this use case)
    lines = source.splitlines(keepends=True)

    # Group violations by function to apply related fixes together
    violations_by_function = {}
    for v in violations:
        violations_by_function.setdefault(v.function_name, []).append(v)

    for function_name, func_violations in violations_by_function.items():
        # Find the function definition line
        for i, line in enumerate(lines):
            if f"def {function_name}" in line or f"async def {function_name}" in line:
                lines = _apply_fixes_to_function(
                    lines, i, function_name, func_violations
                )
                break

    return "".join(lines)


def _apply_fixes_to_function(
    lines: list[str], func_line_idx: int, function_name: str, violations: list
) -> list[str]:
    """
    Apply fixes to a specific function.

    Args:
        lines: Source code lines
        func_line_idx: Index of function definition line
        function_name: Name of the function
        violations: Violations for this function

    Returns:
        Modified lines
    """
    func_line = lines[func_line_idx]
    indent = len(func_line) - len(func_line.lstrip())

    # Check which fixes are needed
    needs_decorator = any(v.rule_id == "action_must_have_decorator" for v in violations)
    needs_return_type = any(
        v.rule_id == "action_must_return_result" for v in violations
    )
    needs_metadata = any(
        v.rule_id == "decorator_missing_required_field" for v in violations
    )

    # Fix 1: Add missing @atomic_action decorator
    if needs_decorator:
        # Infer action_id from function name
        action_id = _infer_action_id(function_name)

        decorator_lines = [
            f'{" " * indent}@atomic_action(\n',
            f'{" " * (indent + 4)}action_id="{action_id}",\n',
            f'{" " * (indent + 4)}intent="Atomic action for {function_name}",\n',
            f'{" " * (indent + 4)}impact=ActionImpact.WRITE_CODE,\n',
            f'{" " * (indent + 4)}policies=["atomic_actions"],\n',
            f'{" " * indent})\n',
        ]
        lines[func_line_idx:func_line_idx] = decorator_lines
        func_line_idx += len(decorator_lines)

    # Fix 2: Add missing return type annotation
    if needs_return_type:
        if " -> " not in lines[func_line_idx] and ":" in lines[func_line_idx]:
            lines[func_line_idx] = lines[func_line_idx].replace(
                ":", " -> ActionResult:", 1
            )

    return lines


def _infer_action_id(function_name: str) -> str:
    """
    Infer action_id from function name.

    Args:
        function_name: Function name (e.g., fix_ids_internal)

    Returns:
        Action ID (e.g., fix.ids)
    """
    # Remove _internal suffix
    name = function_name.replace("_internal", "")

    # Split on underscore and take first two parts
    parts = name.split("_")
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}"

    return f"action.{name}"


def _show_preview(violations: list) -> None:
    """Show what would be fixed."""
    for v in violations:
        print(f"  • {v.rule_id}: {v.message}")
        if v.suggested_fix:
            print(f"    Fix: {v.suggested_fix}")
