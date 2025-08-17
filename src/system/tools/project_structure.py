# src/system/tools/project_structure.py
"""
Utilities for discovering and working with project structure.
"""
import re
from pathlib import Path
from typing import Set

from shared.logger import getLogger

log = getLogger(__name__)


class ProjectStructureError(Exception):
    """Custom exception for when the project's root cannot be determined."""

    pass


def find_project_root(start_path: Path) -> Path:
    """Traverses upward from a starting path to find the project root, marked by 'pyproject.toml'."""
    current_path = start_path.resolve()
    for path in [current_path, *current_path.parents]:
        if (path / "pyproject.toml").exists():
            return path
    raise ProjectStructureError("Could not find 'pyproject.toml'.")


def get_cli_entry_points(root_path: Path) -> Set[str]:
    """Parses pyproject.toml to find declared command-line entry points."""
    pyproject_path = root_path / "pyproject.toml"
    if not pyproject_path.exists():
        return set()

    try:
        content = pyproject_path.read_text(encoding="utf-8")
        match = re.search(r"\[tool\.poetry\.scripts\]([^\[]*)", content, re.DOTALL)
        return set(re.findall(r'=\s*"[^"]+:(\w+)"', match.group(1))) if match else set()
    except (OSError, UnicodeDecodeError) as e:
        log.warning(f"Could not read pyproject.toml: {e}")
        return set()


def should_exclude_path(path: Path, exclude_patterns: list[str]) -> bool:
    """Determines if a given path should be excluded from scanning."""
    return any(pattern in path.parts for pattern in exclude_patterns)


def get_python_files(src_root: Path, exclude_patterns: list[str]) -> list[Path]:
    """Get all Python files in the source directory, excluding specified patterns."""
    # --- THIS IS THE FIX ---
    # The glob operation does not guarantee a specific order. By converting to a
    # list and sorting it, we ensure that the KnowledgeGraphBuilder always
    # processes files in a deterministic, alphabetical order. This eliminates
    # a potential source of environment-specific inconsistencies.
    all_files = list(src_root.rglob("*.py"))
    all_files.sort()

    return [
        f
        for f in all_files
        if f.name != "__init__.py" and not should_exclude_path(f, exclude_patterns)
    ]
