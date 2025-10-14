# src/shared/path_utils.py
"""
Provides utility functions for working with file system paths within the repository structure.
"""

from __future__ import annotations

from pathlib import Path


# ID: d302f037-094f-4573-92d0-39dc29c012f6
def get_repo_root(start_path: Path | None = None) -> Path:
    """Find and return the repository root by locating the .git directory, starting from the current directory or provided path."""
    """
    Find and return the repository root by locating the .git directory.
    Starts from current directory or provided path.

    Returns:
        Path: Absolute path to repo root.

    Raises:
        RuntimeError: If no .git directory is found.
    """
    current = Path(start_path or Path.cwd()).resolve()

    # Traverse upward until .git is found
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent

    raise RuntimeError("Not a git repository: could not find .git directory")
