# src/shared/utils/path_utils.py

"""
Path Utilities - Reusable File Discovery and Pattern Matching

CONSTITUTIONAL ALIGNMENT:
- DRY-by-Design: Eliminates duplication across validators and scanners
- Used by: IntentSchemaValidator, PathValidator, file handlers
- Consistent file discovery patterns

Consolidates common patterns from:
- IntentSchemaValidator._iter_intent_yaml()
- PathValidator._matches_pattern()
- Various file scanning operations
"""

from __future__ import annotations

from pathlib import Path

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: iter_files_by_extension
# ID: 1a2b3c4d-5e6f-7890-abcd-ef1234567890
def iter_files_by_extension(
    root: Path,
    extensions: tuple[str, ...],
    exclude_prefixes: tuple[str, ...] = (),
    recursive: bool = True,
) -> list[Path]:
    """
    Discover files by extension with exclusion support.

    Args:
        root: Root directory to search
        extensions: File extensions to include (e.g., ('.yaml', '.yml'))
        exclude_prefixes: Path prefixes to exclude (relative to root)
        recursive: Whether to search recursively (default: True)

    Returns:
        Sorted list of matching file paths

    Example:
        # Find all YAML files except in runtime/
        files = iter_files_by_extension(
            Path('.intent'),
            ('.yaml', '.yml'),
            exclude_prefixes=('runtime/', 'exports/')
        )
    """
    if not root.exists():
        logger.warning("Root directory does not exist: %s", root)
        return []

    files: list[Path] = []
    seen: set[Path] = set()

    # Build glob patterns for each extension
    patterns = [f"**/*{ext}" if recursive else f"*{ext}" for ext in extensions]

    for pattern in patterns:
        for path in root.glob(pattern):
            # Skip duplicates (same file matched by multiple patterns)
            if path in seen:
                continue

            # Check exclusions
            try:
                rel = path.relative_to(root).as_posix()
                if any(rel.startswith(prefix) for prefix in exclude_prefixes):
                    continue
            except ValueError:
                # Path is not relative to root, skip
                continue

            seen.add(path)
            files.append(path)

    return sorted(files)


# ID: iter_python_files
# ID: 2b3c4d5e-6f7a-8901-bcde-f12345678901
def iter_python_files(
    root: Path,
    exclude_prefixes: tuple[str, ...] = (),
) -> list[Path]:
    """
    Discover Python files with common exclusions.

    Convenience wrapper for iter_files_by_extension with Python defaults.

    Args:
        root: Root directory to search
        exclude_prefixes: Additional prefixes to exclude (added to defaults)

    Returns:
        Sorted list of .py files

    Example:
        files = iter_python_files(Path('src'), exclude_prefixes=('legacy/',))
    """
    # Common Python exclusions
    default_excludes = (
        ".venv/",
        "venv/",
        "__pycache__/",
        ".git/",
        "node_modules/",
        ".pytest_cache/",
        ".mypy_cache/",
        ".ruff_cache/",
    )

    all_excludes = default_excludes + exclude_prefixes

    return iter_files_by_extension(
        root, extensions=(".py",), exclude_prefixes=all_excludes
    )


# ID: matches_glob_pattern
# ID: 3c4d5e6f-7a8b-9012-cdef-123456789012
def matches_glob_pattern(path: str | Path, pattern: str) -> bool:
    """
    Check if path matches glob pattern.

    Args:
        path: File path (string or Path object)
        pattern: Glob pattern (e.g., 'src/**/*.py', '*.yaml')

    Returns:
        True if path matches pattern

    Example:
        matches_glob_pattern('src/main.py', 'src/**/*.py')  # True
        matches_glob_pattern('tests/test.py', 'src/**/*.py')  # False
    """
    if not pattern:
        return False

    if isinstance(path, str):
        path = Path(path)

    return path.match(pattern)


# ID: matches_any_pattern
# ID: 4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a
def matches_any_pattern(path: str | Path, patterns: list[str]) -> bool:
    """
    Check if path matches any of multiple patterns.

    Args:
        path: File path to check
        patterns: List of glob patterns

    Returns:
        True if path matches at least one pattern

    Example:
        matches_any_pattern(
            'src/main.py',
            ['src/**/*.py', 'tests/**/*.py']
        )  # True
    """
    return any(matches_glob_pattern(path, pattern) for pattern in patterns)


# ID: safe_relative_to
# ID: 5e6f7a8b-9c0d-1e2f-3a4b-5c6d7e8f9a0b
def safe_relative_to(path: Path, root: Path) -> str | None:
    """
    Get relative path string, returning None if not relative.

    Args:
        path: Path to make relative
        root: Root to make relative to

    Returns:
        Relative path as POSIX string, or None if path is not under root

    Example:
        safe_relative_to(Path('/repo/src/main.py'), Path('/repo'))
        # Returns: 'src/main.py'

        safe_relative_to(Path('/other/file.py'), Path('/repo'))
        # Returns: None
    """
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


# ID: is_under_directory
# ID: 6f7a8b9c-0d1e-2f3a-4b5c-6d7e8f9a0b1c
def is_under_directory(path: Path, directory: Path) -> bool:
    """
    Check if path is under directory (direct child or nested).

    Args:
        path: Path to check
        directory: Directory to check against

    Returns:
        True if path is under directory

    Example:
        is_under_directory(Path('/repo/src/main.py'), Path('/repo'))
        # True

        is_under_directory(Path('/repo/src/main.py'), Path('/repo/src'))
        # True

        is_under_directory(Path('/other/file.py'), Path('/repo'))
        # False
    """
    try:
        path_resolved = path.resolve()
        dir_resolved = directory.resolve()
        return dir_resolved in path_resolved.parents or path_resolved == dir_resolved
    except (ValueError, OSError):
        return False


# ID: ensure_posix_path
# ID: 7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d
def ensure_posix_path(path: str | Path) -> str:
    """
    Ensure path uses POSIX format (forward slashes).

    Cross-platform utility to normalize path separators.

    Args:
        path: Path to normalize

    Returns:
        Path string with forward slashes

    Example:
        ensure_posix_path('src\\windows\\path.py')
        # Returns: 'src/windows/path.py'
    """
    if isinstance(path, str):
        path = Path(path)
    return path.as_posix()
