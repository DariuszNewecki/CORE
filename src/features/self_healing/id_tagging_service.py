# src/features/self_healing/id_tagging_service.py
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
    missing an '# ID:' tag, and adds a new UUID tag to them.
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

                    # Use the new, robust utility to find the ID and definition line
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
        console.print(
            "[bold green]✅ All governable public symbols already have IDs.[/bold green]"
        )
        return 0

    for file_path, fixes in files_to_fix.items():
        console.print(
            f"🔧 Processing file: [cyan]{file_path.relative_to(settings.REPO_PATH)}[/cyan]"
        )
        fixes.sort(key=lambda x: x["line_number"], reverse=True)

        if dry_run:
            for fix in fixes:
                console.print(
                    f"   -> [DRY RUN] Would assign new ID to '{fix['name']}' at line {fix['line_number']}"
                )
                total_ids_assigned += 1
            continue

        try:
            lines = file_path.read_text("utf-8").splitlines()
            for fix in fixes:
                # The line number from our utility is the 'def' or 'class' line
                line_index = fix["line_number"] - 1
                original_line = lines[line_index]
                indentation = len(original_line) - len(original_line.lstrip(" "))

                new_id = str(uuid.uuid4())
                tag_line = f"{' ' * indentation}# ID: {new_id}"

                # Insert the tag immediately before the definition line
                lines.insert(line_index, tag_line)
                total_ids_assigned += 1

            file_path.write_text("\n".join(lines) + "\n", "utf-8")
            console.print(f"   -> ✅ Assigned {len(fixes)} new ID(s).")
        except Exception as e:
            console.print(
                f"   -> [bold red]❌ Error writing to {file_path}: {e}[/bold red]"
            )

    console.print("\n--- ID Assignment Complete ---")
    if dry_run:
        console.print(
            f"💧 DRY RUN: Found {total_ids_assigned} public symbols that need an ID."
        )
        console.print("   Run with '--write' to apply these changes.")
    else:
        console.print(
            f"✅ APPLIED: Successfully assigned {total_ids_assigned} new IDs."
        )
        # --- THIS IS THE FIX ---
        # Updated the command to the new, correct one.
        console.print(
            "\n[bold]NEXT STEP:[/bold] Run 'poetry run core-admin manage database sync-knowledge --write' to update the database."
        )
        # --- END OF FIX ---

    return total_ids_assigned
