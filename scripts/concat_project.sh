#!/usr/bin/env python3
# scripts/concat_project.sh
"""
A constitutionally-aware script to bundle the CORE project's essence for AI review.
It includes the Mind, Body, and operational tooling while excluding transient state,
sensitive data, and generated artifacts. It produces a structured output for clarity.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Use `tomllib` for modern TOML parsing, available in Python 3.11+
# For older versions, this would require `pip install tomli`
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

# --- Configuration ---
OUTPUT_FILE = "project_context.txt"
ROOT_MARKER = "pyproject.toml"

# Define what to exclude, based on our architectural principles.
EXCLUDE_PATTERNS = [
    ".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache",
    "logs", "sandbox", "pending_writes", "demo", "work", "dist", "build",
    ".env", ".intent/keys", "poetry.lock",
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.ico", "*.pyc", "*.so",
    "*.DS_Store", "Thumbs.db",
]
# --- End Configuration ---


def is_excluded(path: Path, root: Path, exclude_patterns: list[str]) -> bool:
    """Check if a path should be excluded based on the patterns."""
    relative_path_str = str(path.relative_to(root))
    for pattern in exclude_patterns:
        if path.match(pattern) or relative_path_str.startswith(pattern):
            return True
    return False

def is_likely_binary(path: Path) -> bool:
    """Heuristic to check if a file is binary by looking for null bytes."""
    try:
        with path.open("rb") as f:
            return b"\x00" in f.read(1024)
    except Exception:
        return True

def get_include_dirs_from_pyproject(root: Path) -> list[str]:
    """Reads pyproject.toml to get the list of source directories."""
    pyproject_path = root / ROOT_MARKER
    config = tomllib.loads(pyproject_path.read_text("utf-8"))
    packages = config.get("tool", {}).get("poetry", {}).get("packages", [])
    
    # Extract the 'include' value from each package dictionary
    source_dirs = {pkg["include"] for pkg in packages if "include" in pkg}
    
    # Add other key directories that are not formal packages
    return sorted(list(source_dirs | {".intent", "tests", "scripts", "sql"}))

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Generate Project Context Bundle for AI review.")
    parser.add_argument(
        "--output", default=OUTPUT_FILE, help="Path for the output bundle file."
    )
    args = parser.parse_args()
    output_path = Path(args.output).resolve()

    root_path = Path.cwd()
    if not (root_path / ROOT_MARKER).exists():
        print(f"❌ Error: This script must be run from the CORE project root directory.")
        return 1

    print(f"🚀 Generating Project Context Bundle for AI review...")

    # --- START OF AMENDMENT: Declarative directory discovery ---
    include_dirs = get_include_dirs_from_pyproject(root_path)
    print(f"   -> Including source directories from pyproject.toml: {include_dirs}")
    
    include_root_files = [
        "pyproject.toml", "README.md", "CONTRIBUTING.md", "LICENSE", "Makefile",
        ".gitignore", "assesment.prompt", "docker-compose.yml"
    ]
    # --- END OF AMENDMENT ---
    
    final_exclude_patterns = EXCLUDE_PATTERNS + [str(output_path.relative_to(root_path))]

    files_to_bundle = []
    for dir_name in include_dirs:
        dir_path = root_path / dir_name
        if dir_path.is_dir():
            files_to_bundle.extend(dir_path.rglob("*"))

    for file_name in include_root_files:
        file_path = root_path / file_name
        if file_path.is_file():
            files_to_bundle.append(file_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    file_count = 0
    with output_path.open("w", encoding="utf-8") as outfile:
        outfile.write("--- START OF FILE project_context.txt ---\n\n")
        outfile.write("--- START OF PROJECT CONTEXT BUNDLE ---\n\n")

        unique_files = sorted(list(set(files_to_bundle)))

        for file in unique_files:
            if (
                not file.is_file()
                or is_excluded(file, root_path, final_exclude_patterns)
                or is_likely_binary(file)
            ):
                continue

            file_count += 1
            relative_path = file.relative_to(root_path)
            outfile.write(f"--- START OF FILE ./{relative_path} ---\n")
            try:
                content = file.read_text("utf-8")
                if content:
                    outfile.write(content)
                else:
                    outfile.write("[EMPTY FILE]")
            except Exception as e:
                outfile.write(f"[ERROR READING FILE: {e}]")
            outfile.write(f"\n--- END OF FILE ./{relative_path} ---\n\n")

        outfile.write("--- END OF PROJECT CONTEXT BUNDLE ---\n")

    print(f"\n✅ Done. Concatenated {file_count} files into {output_path}.")
    return 0

if __name__ == "__main__":
    sys.exit(main())