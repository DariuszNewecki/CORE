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


# ID: b9dc098f-9473-4329-890b-d12b4cef2ba9
# ID: 2e0fab8f-21a4-48a6-b553-5fdd0eb8f83a
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


# ID: 8337e50c-7288-479b-8bf1-f81aa4ec1648
# ID: a27f169d-50b6-4047-bcc0-748bf6a1e0ca
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


# ID: 466742f0-cf59-4d91-8b62-93824c7a9335
# ID: e6c4b600-3acd-47ed-828b-6e43fde88745
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


# ID: 3ec19814-e92d-4619-91b2-3f6d8b59e762
# ID: 175cbfee-3c49-4280-be81-457e2f17660b
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


# ID: b5d61ae6-7067-47ed-baaf-ea649c182dd1
# ID: 4f468352-328a-499c-9062-bb6e38b2af7f
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


# ID: f04261e4-2c19-4ace-9bab-aa7b3e2468f4
# ID: 62f5898e-3e7e-4690-8ef4-34a8b944e3b1
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


# ID: 8f7ddbfa-f669-4513-a47c-3cb66531d244
# ID: 823eb957-54db-4cef-ba08-0b790a427795
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
