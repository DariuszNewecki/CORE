# src/features/self_healing/id_tagging_service.py
"""Provides functionality for the id_tagging_service module."""

from __future__ import annotations

import ast
import uuid
from collections import defaultdict

from rich.console import Console

from shared.ast_utility import find_symbol_id_and_def_line
from shared.config import settings

console = Console()


def _is_public(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> bool:
    """Determines if a symbol is public (not starting with _ or a dunder)."""
    is_dunder = node.name.startswith("__") and node.name.endswith("__")
    return not node.name.startswith("_") and not is_dunder


# ID: 38f29597-95bb-4e6c-aabb-72baaf841522
def assign_missing_ids(dry_run: bool = True) -> int:
    """
    Scans all Python files in the 'src/' directory, finds public symbols
    missing an '# ID:' tag, and adds a new UUID tag to them. Returns the count.
    """
    src_dir = settings.REPO_PATH / "src"
    files_to_process = list(src_dir.rglob("*.py"))
    total_ids_assigned = 0
    files_to_fix = defaultdict(list)

    for file_path in files_to_process:
        try:
            content = file_path.read_text("utf-8")
            source_lines = content.splitlines()
            tree = ast.parse(content, filename=str(file_path))

            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    if not _is_public(node):
                        continue

                    id_result = find_symbol_id_and_def_line(node, source_lines)

                    if not id_result.has_id:
                        files_to_fix[file_path].append(
                            {
                                "line_number": id_result.definition_line_num,
                                "name": node.name,
                            }
                        )
        except Exception as e:
            console.print(
                f"   -> [bold red]❌ Error processing {file_path}: {e}[/bold red]"
            )

    if not files_to_fix:
        return 0

    for file_path, fixes in files_to_fix.items():
        fixes.sort(key=lambda x: x["line_number"], reverse=True)

        if dry_run:
            total_ids_assigned += len(fixes)
            continue

        try:
            lines = file_path.read_text("utf-8").splitlines()
            for fix in fixes:
                line_index = fix["line_number"] - 1
                original_line = lines[line_index]
                indentation = len(original_line) - len(original_line.lstrip(" "))

                new_id = str(uuid.uuid4())
                tag_line = f"{' ' * indentation}# ID: {new_id}"

                lines.insert(line_index, tag_line)
                total_ids_assigned += 1

            file_path.write_text("\n".join(lines) + "\n", "utf-8")
        except Exception as e:
            console.print(
                f"   -> [bold red]❌ Error writing to {file_path}: {e}[/bold red]"
            )

    return total_ids_assigned
