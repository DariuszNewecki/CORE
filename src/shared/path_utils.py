# src/shared/path_utils.py

"""Provides functionality for the path_utils module."""

from __future__ import annotations

from pathlib import Path


# ID: 4feaf13b-3445-46b3-941f-2258e5cba309
def copy_tree(src: Path, dst: Path, exclude: list[str] | None = None):
    """
    Recursively copies a directory tree, skipping specified directory names.
    """
    if exclude is None:
        exclude = [".git", ".venv", "venv", "__pycache__", "work", "reports"]

    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.name in exclude:
            continue

        s = src / item.name
        d = dst / item.name
        if s.is_dir():
            copy_tree(s, d, exclude)
        else:
            # FIX: The original file content was not being written.
            d.write_bytes(s.read_bytes())


# ID: 897908af-e0f8-4836-aa93-df0bdaac56d1
def copy_file(src: Path, dst: Path):
    """
    Copies a single file, creating the destination parent directory if needed.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    # FIX: The original file content was not being written.
    dst.write_bytes(src.read_bytes())


# RENAMED: Changed from find_project_root to get_repo_root to match existing imports.
# ID: aef59564-a300-45e0-ba8e-ec19b7d5c6a5
def get_repo_root(start_dir: Path | None = None) -> Path:
    """
    Find the project root by looking for the `.intent` directory.
    """
    if start_dir is None:
        start_dir = Path.cwd()
    current_path = start_dir
    # Recurse upwards until the root of the filesystem is reached
    while current_path != current_path.parent:
        if (current_path / ".intent").is_dir():
            return current_path
        current_path = current_path.parent

    # Check the final path (e.g., '/') as well
    if (current_path / ".intent").is_dir():
        return current_path

    raise FileNotFoundError("Project root with .intent directory not found.")
