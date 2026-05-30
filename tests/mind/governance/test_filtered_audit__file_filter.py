"""Tests for run_filtered_audit / execute_rule file scoping (#279).

Closes the gap that blocked the pre-commit hook story: per-file rules
can now be scoped to a specific file list via --files; context-level
rules skip with a warning when that scope is active because they look
at the whole repo and can't be meaningfully filtered.

The path-normalization helper accepts repo-relative, ./-prefixed, and
absolute paths and rejects anything outside the repo root.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mind.governance.filtered_audit import normalize_file_filter


def test_normalize_returns_none_for_empty_input(tmp_path: Path) -> None:
    assert normalize_file_filter(None, tmp_path) is None
    assert normalize_file_filter([], tmp_path) is None


def test_normalize_handles_repo_relative_paths(tmp_path: Path) -> None:
    """A repo-relative POSIX path stays as-is in the filter set."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "foo.py").touch()
    result = normalize_file_filter(["src/foo.py"], tmp_path)
    assert result == frozenset({"src/foo.py"})


def test_normalize_handles_dot_prefixed_paths(tmp_path: Path) -> None:
    """./-prefixed paths normalize to plain repo-relative form."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "bar.py").touch()
    result = normalize_file_filter(["./src/bar.py"], tmp_path)
    assert result == frozenset({"src/bar.py"})


def test_normalize_handles_absolute_paths(tmp_path: Path) -> None:
    """Absolute paths inside the repo are converted to repo-relative."""
    (tmp_path / "src").mkdir()
    abs_path = tmp_path / "src" / "baz.py"
    abs_path.touch()
    result = normalize_file_filter([str(abs_path)], tmp_path)
    assert result == frozenset({"src/baz.py"})


def test_normalize_handles_mixed_input(tmp_path: Path) -> None:
    """Repo-relative + absolute in the same call collapse to the same set."""
    (tmp_path / "src").mkdir()
    a = tmp_path / "src" / "a.py"
    b = tmp_path / "src" / "b.py"
    a.touch()
    b.touch()
    result = normalize_file_filter([str(a), "src/b.py"], tmp_path)
    assert result == frozenset({"src/a.py", "src/b.py"})


def test_normalize_rejects_paths_outside_repo(tmp_path: Path) -> None:
    """Silently dropping out-of-repo paths would mask user error and
    produce a confusing empty audit; the helper raises loudly instead.
    """
    other = tmp_path.parent / "elsewhere.py"
    with pytest.raises(ValueError, match="outside the repository root"):
        normalize_file_filter([str(other)], tmp_path)


def test_normalize_deduplicates(tmp_path: Path) -> None:
    """The same file passed twice in different forms collapses to one entry."""
    (tmp_path / "src").mkdir()
    abs_path = tmp_path / "src" / "dup.py"
    abs_path.touch()
    result = normalize_file_filter(
        [str(abs_path), "src/dup.py", "./src/dup.py"], tmp_path
    )
    assert result == frozenset({"src/dup.py"})


def test_normalize_rejects_absolute_dot_dot_traversal(tmp_path: Path) -> None:
    """Absolute path with `..` that escapes repo_root must be rejected
    (CodeQL py/path-injection). Pre-fix, the absolute branch skipped
    .resolve() and `relative_to(repo_root)` was purely lexical — a path
    like `/<repo>/x/../../etc/passwd` lexically starts with `/<repo>` and
    sneaked past the boundary check.
    """
    escape = tmp_path / "x" / ".." / ".." / "outside.py"
    with pytest.raises(ValueError, match="outside the repository root"):
        normalize_file_filter([str(escape)], tmp_path)


def test_normalize_rejects_absolute_symlink_to_outside_repo(tmp_path: Path) -> None:
    """Absolute symlink lexically inside repo_root but pointing outside
    must be rejected (CodeQL py/path-injection). Resolving before
    relative_to follows the symlink and surfaces the real target.
    """
    (tmp_path / "src").mkdir()
    outside_target = tmp_path.parent / "outside_target.py"
    outside_target.touch()
    symlink = tmp_path / "src" / "innocent.py"
    symlink.symlink_to(outside_target)
    with pytest.raises(ValueError, match="outside the repository root"):
        normalize_file_filter([str(symlink)], tmp_path)
