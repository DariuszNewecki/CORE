# src/body/self_healing/atomic_actions_fixer.py
"""
Source-level fixer for atomic-action pattern violations.

Moved from src/cli/commands/fix/atomic_actions.py under ADR-050 (Body
must not import from CLI). The CLI module retains a deprecated re-export
shim for the public entry point; helpers are private to this module.

The fixer operates as a pure source transformation: given a Python
source string and a list of violations, returns the rewritten source
with missing @atomic_action decorators and ActionResult return types
inserted, plus mandatory imports added.
"""

from __future__ import annotations

from pathlib import Path


# ID: 7b1c4661-73dd-4200-98c7-57c56a95f51e
def fix_file_violations(source: str, violations: list, file_path: Path) -> str:
    """
    Fix all violations in a single file and ensure imports exist.
    """
    lines = source.splitlines(keepends=True)
    violations_by_function = {}
    for v in violations:
        violations_by_function.setdefault(v.function_name, []).append(v)
    for function_name, func_violations in violations_by_function.items():
        for i, line in enumerate(lines):
            if f"def {function_name}" in line or f"async def {function_name}" in line:
                lines = _apply_fixes_to_function(
                    lines, i, function_name, func_violations
                )
                break
    if violations:
        lines = _ensure_imports(lines)
    return "".join(lines)


def _ensure_imports(lines: list[str]) -> list[str]:
    """Ensures mandatory atomic action imports exist at the top of the file."""
    content = "".join(lines)
    new_imports = []
    if "from shared.atomic_action import atomic_action" not in content:
        new_imports.append("from shared.atomic_action import atomic_action\n")
    if "from shared.action_types import ActionImpact" not in content:
        if (
            "from shared.action_types import" in content
            and "ActionImpact" not in content
        ):
            for i, line in enumerate(lines):
                if "from shared.action_types import" in line:
                    lines[i] = line.replace("import ", "import ActionImpact, ")
                    break
        else:
            new_imports.append(
                "from shared.action_types import ActionImpact, ActionResult\n"
            )
    if not new_imports:
        return lines
    insert_idx = 0
    for i, line in enumerate(lines):
        if "from __future__" in line:
            insert_idx = i + 1
        elif line.startswith("#"):
            continue
        else:
            break
    return [*lines[:insert_idx], "\n", *new_imports, *lines[insert_idx:]]


def _apply_fixes_to_function(
    lines: list[str], func_line_idx: int, function_name: str, violations: list
) -> list[str]:
    """
    Apply fixes to a specific function definition.
    """
    func_line = lines[func_line_idx]
    indent = len(func_line) - len(func_line.lstrip())
    needs_decorator = any(v.rule_id == "action_must_have_decorator" for v in violations)
    needs_return_type = any(
        v.rule_id == "action_must_return_result" for v in violations
    )
    if needs_decorator:
        action_id = _infer_action_id(function_name)
        decorator_lines = [
            f"{' ' * indent}@atomic_action(\n",
            f'{" " * (indent + 4)}action_id="{action_id}",\n',
            f'{" " * (indent + 4)}intent="Atomic action for {function_name}",\n',
            f"{' ' * (indent + 4)}impact=ActionImpact.WRITE_CODE,\n",
            f'{" " * (indent + 4)}policies=["atomic_actions"],\n',
            f"{' ' * indent})\n",
        ]
        lines[func_line_idx:func_line_idx] = decorator_lines
        func_line_idx += len(decorator_lines)
    if needs_return_type:
        if " -> " not in lines[func_line_idx] and ":" in lines[func_line_idx]:
            lines[func_line_idx] = lines[func_line_idx].replace(
                ":", " -> ActionResult:", 1
            )
    return lines


def _infer_action_id(function_name: str) -> str:
    """
    Infers action_id from function name (category.name).
    """
    name = function_name.replace("_internal", "").replace("action_", "")
    parts = name.split("_")
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}"
    return f"action.{name}"
