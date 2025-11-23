# scripts/refactor_remove_function.py
"""
A syntax-aware refactoring tool to safely remove a top-level function
from multiple Python files.

Usage:
  poetry run python scripts/refactor_remove_function.py <function_name> <file_or_glob_1> <file_or_glob_2> ...

Example:
  poetry run python scripts/refactor_remove_function.py register "src/cli/logic/*.py" "src/cli/commands/*.py"
"""

import ast
import sys
from pathlib import Path


def remove_function_from_file(file_path: Path, function_name: str) -> bool:
    """
    Parses a Python file, removes the specified top-level function,
    and overwrites the file if changes were made.

    Returns True if the file was modified, False otherwise.
    """
    try:
        original_source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(original_source)

        # Filter out top-level functions with the matching name
        original_body_len = len(tree.body)
        new_body = [
            node
            for node in tree.body
            if not (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == function_name
            )
        ]

        # Only rewrite the file if a function was actually removed
        if len(new_body) < original_body_len:
            new_tree = ast.Module(body=new_body, type_ignores=tree.type_ignores)
            # Use ast.unparse for clean, formatted output
            new_source = ast.unparse(new_tree)
            file_path.write_text(new_source + "\n", encoding="utf-8")
            return True
        return False

    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}", file=sys.stderr)
        return False


def main():
    """Main entry point for the script."""
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    function_to_remove = sys.argv[1]
    file_globs = sys.argv[2:]

    print(f"🔍 Searching for and removing top-level function '{function_to_remove}'...")

    files_to_process = []
    for glob_pattern in file_globs:
        files_to_process.extend(Path.cwd().glob(glob_pattern))

    if not files_to_process:
        print("No files found matching the provided patterns.")
        return

    modified_count = 0
    for file_path in sorted(list(set(files_to_process))):
        if file_path.is_file():
            if remove_function_from_file(file_path, function_to_remove):
                print(f"✅ Refactored: {file_path}")
                modified_count += 1

    print(f"\n✨ Refactoring complete. Modified {modified_count} file(s).")


if __name__ == "__main__":
    main()
