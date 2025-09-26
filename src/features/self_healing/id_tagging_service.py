# src/features/self_healing/id_tagging_service.py
from __future__ import annotations

import ast
import uuid
from collections import defaultdict

from rich.console import Console

from shared.config import settings

console = Console()


def _is_public(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> bool:
    """Determines if a symbol is public (not starting with an underscore)."""
    return not node.name.startswith("_")


# ID: 38f29597-95bb-4e6c-aabb-72baaf841522
def assign_missing_ids(dry_run: bool = True) -> int:
    """
    Scans all Python files in the 'src/' directory, finds public symbols
    missing an '# ID:' tag, and adds a new UUID tag to them.

    Args:
        dry_run: If True, only reports on the changes that would be made.

    Returns:
        The total number of new IDs that were (or would be) assigned.
    """
    src_dir = settings.REPO_PATH / "src"
    files_to_process = list(src_dir.rglob("*.py"))
    total_ids_assigned = 0

    files_to_fix = defaultdict(list)

    for file_path in files_to_process:
        try:
            content = file_path.read_text("utf-8")
            source_lines = content.splitlines()
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    if not _is_public(node):
                        continue

                    # Check the line above the symbol definition for an existing ID tag
                    tag_line_index = node.lineno - 2
                    has_id = False
                    if 0 <= tag_line_index < len(source_lines):
                        line_above = source_lines[tag_line_index].strip()
                        if line_above.startswith("# ID:"):
                            has_id = True

                    if not has_id:
                        # Found a public symbol that needs an ID
                        files_to_fix[file_path].append(
                            {"line_number": node.lineno, "name": node.name}
                        )
        except Exception as e:
            console.print(
                f"   -> [bold red]❌ Error processing {file_path}: {e}[/bold red]"
            )

    if not files_to_fix:
        console.print(
            "[bold green]✅ All public symbols already have IDs.[/bold green]"
        )
        return 0

    for file_path, fixes in files_to_fix.items():
        console.print(
            f"🔧 Processing file: [cyan]{file_path.relative_to(settings.REPO_PATH)}[/cyan]"
        )

        # Sort fixes by line number in reverse to safely insert new lines
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
                # Get indentation from the function definition line
                line_index = fix["line_number"] - 1
                original_line = lines[line_index]
                indentation = len(original_line) - len(original_line.lstrip(" "))

                # Generate new ID and format the tag line
                new_id = str(uuid.uuid4())
                tag_line = f"{' ' * indentation}# ID: {new_id}"

                # Insert the new tag line
                lines.insert(line_index, tag_line)
                total_ids_assigned += 1

            file_path.write_text("\n".join(lines) + "\n", "utf-8")
            console.print(f"   -> ✅ Assigned {len(fixes)} new ID(s).")
        except Exception as e:
            console.print(
                f"   -> [bold red]❌ Error writing to {file_path}: {e}[/bold red]"
            )

    return total_ids_assigned
