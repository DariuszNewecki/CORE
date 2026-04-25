# src/shared/utils/glob_match.py

"""
Glob matching with gitignore semantics.

Single entry point for path-pattern evaluation across src/. Replaces
direct pathlib.Path.match() usage, which on Python 3.12 has two surprising
semantics that produced silent under-enforcement at security-sensitive
sites: ** is treated as single-segment *, and matching is suffix-only.

Per ADR-012, all in-scope src/ call sites use these helpers; the
audit_context.py compensation helpers (_include_matches, _is_excluded)
are out of scope for this ADR and migrate separately under issue #117.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from pathspec.patterns.gitwildmatch import GitWildMatchPattern


# ID: 57255383-a41d-4c3e-b003-dd5ba8ce622f
def matches_glob(path: str | Path, pattern: str) -> bool:
    """
    Test whether a path matches a glob pattern under gitignore semantics.

    Uses pathspec's GitWildMatchPattern. Patterns follow gitignore.5
    conventions: leading or middle '/' anchors at root; '*' matches any
    run of characters except '/'; '**' matches any number of path
    segments including zero; trailing '/' restricts to directories.

    Args:
        path: Path-like object or string. Converted to POSIX form for
            consistent matching across platforms.
        pattern: Glob pattern string. Empty patterns return False.

    Returns:
        True if the path matches the pattern, False otherwise.

    Examples:
        >>> matches_glob("src/main.py", "src/**/*.py")
        True
        >>> matches_glob("src/api/sub/main.py", "src/**/*.py")
        True
        >>> matches_glob("var/secrets/k.txt", "**/secrets/**")
        True
        >>> matches_glob("var/secrets/k.txt", "secrets/*")
        False
    """
    if not pattern:
        return False

    if isinstance(path, Path):
        path_str = path.as_posix()
    else:
        path_str = str(path).replace("\\", "/")

    compiled = GitWildMatchPattern(pattern)
    regex = compiled.regex
    if regex is None:
        return False
    return bool(regex.match(path_str))


# ID: b5d94dcf-5791-41a0-834f-8b2aa25b32f2
def matches_any_glob(path: str | Path, patterns: Iterable[str]) -> bool:
    """
    Test whether a path matches any of multiple glob patterns.

    Args:
        path: Path-like object or string.
        patterns: Iterable of pattern strings.

    Returns:
        True if the path matches at least one pattern.

    Examples:
        >>> matches_any_glob("var/secrets/k.txt", ["**/.env", "**/secrets/**"])
        True
    """
    return any(matches_glob(path, pat) for pat in patterns)
