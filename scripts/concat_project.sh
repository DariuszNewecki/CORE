#!/usr/bin/env python3
# scripts/create_project_bundle.py
"""
A constitutionally-aware script to bundle the CORE project's essence for AI review.
It includes the Mind, Body, and operational tooling while excluding transient state,
sensitive data, and generated artifacts. It produces a structured output for clarity.
"""
from __future__ import annotations

import argparse
from pathlib import Path

# --- Configuration ---
# The final output file for the bundle.
OUTPUT_FILE = "project_context.txt"
# The marker for the project root.
ROOT_MARKER = "pyproject.toml"

# --- CHANGE: Simplified and corrected include lists ---
# All directories to be included are now in a single list.
INCLUDE_DIRS = [
    ".intent",
    "src",
    "tests",
    "scripts",
    ".github",
    "sql",  # <-- CRITICAL FIX: Added the sql directory
]
# All individual files at the root level are in this list.
INCLUDE_ROOT_FILES = [
    "pyproject.toml", "README.md", "CONTRIBUTING.md", "LICENSE", "Makefile",
    ".gitignore", "assesment.prompt", "docker-compose.yml"
]
# --- END CHANGE ---

# Define what to exclude, based on our architectural principles.
EXCLUDE_PATTERNS = [
    # General exclusions
    ".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache",
    "logs", "sandbox", "pending_writes", "demo", "work", "dist", "build",
    # Sensitive files
    ".env", ".intent/keys",
    # Generated or large artifacts
    "poetry.lock",
    # --- CHANGE: Removed 'reports/' as we only need to exclude the output file ---
    # Binary file extensions
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


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Generate Project Context Bundle for AI review.")
    parser.add_argument(
        "--output", default=OUTPUT_FILE, help="Path for the output bundle file."
    )
    args = parser.parse_args()
    output_path = Path(args.output).resolve()

    # 1. Ensure the script is run from the project root.
    root_path = Path.cwd()
    if not (root_path / ROOT_MARKER).exists():
        print(f"❌ Error: This script must be run from the CORE project root directory.")
        return 1

    print(f"🚀 Generating Project Context Bundle for AI review...")
    print(f"   -> Output will be saved to: {output_path}")

    # Exclude the output file itself
    final_exclude_patterns = EXCLUDE_PATTERNS + [str(output_path)]

    files_to_bundle = []
    # Gather all files from included directories
    for dir_name in INCLUDE_DIRS:
        dir_path = root_path / dir_name
        if dir_path.is_dir():
            files_to_bundle.extend(dir_path.rglob("*"))

    # Add root files
    for file_name in INCLUDE_ROOT_FILES:
        file_path = root_path / file_name
        if file_path.is_file():
            files_to_bundle.append(file_path)

    # 2. Filter, sort, and process files
    output_path.parent.mkdir(parents=True, exist_ok=True)
    file_count = 0
    with output_path.open("w", encoding="utf-8") as outfile:
        outfile.write("--- START OF FILE project_context.txt ---\n\n")
        outfile.write("--- START OF PROJECT CONTEXT BUNDLE ---\n\n")

        # Use a set for efficient deduplication, then sort for deterministic order
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
            outfile.write(f"--- START OF FILE ./{relative_path} ---\n") # <-- Added './' for clarity
            try:
                content = file.read_text("utf-8")
                if content:
                    outfile.write(content)
                else:
                    outfile.write("[EMPTY FILE]")
            except Exception as e:
                outfile.write(f"[ERROR READING FILE: {e}]")
            outfile.write(f"\n--- END OF FILE ./{relative_path} ---\n\n") # <-- Added './' for clarity

        outfile.write("--- END OF PROJECT CONTEXT BUNDLE ---\n")

    print(f"\n✅ Done. Concatenated {file_count} files into {output_path}.")
    return 0

if __name__ == "__main__":
    exit(main())