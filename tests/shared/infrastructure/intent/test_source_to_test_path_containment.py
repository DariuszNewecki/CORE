# tests/shared/infrastructure/intent/test_source_to_test_path_containment.py
"""#817: source_file/target_file path-traversal hardening.

source_to_test_path's prefix check ("must start with src/") is textual only
— "src/../../../etc/passwd" passes it while resolving well outside the repo.
resolve_contained_source_path closes the gap at the filesystem-resolution
call sites that check existence directly, before (or without ever) calling
source_to_test_path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.infrastructure.intent.test_coverage_paths import (
    resolve_contained_source_path,
    source_to_test_path,
)


_CONFIG = {
    "source_root": "src",
    "test_root": "tests",
    "test_file_suffix": "/test_generated.py",
}


def test_source_to_test_path_maps_normal_file() -> None:
    assert (
        source_to_test_path("src/foo/bar.py", _CONFIG)
        == "tests/foo/bar/test_generated.py"
    )


def test_source_to_test_path_rejects_missing_prefix() -> None:
    with pytest.raises(ValueError, match="does not start with"):
        source_to_test_path("lib/foo/bar.py", _CONFIG)


def test_source_to_test_path_rejects_traversal_segments() -> None:
    with pytest.raises(ValueError, match=r"'\.\.' path segments"):
        source_to_test_path("src/../../../etc/passwd", _CONFIG)


def test_source_to_test_path_rejects_traversal_even_when_final_segment_is_legit() -> None:
    """A traversal string can still textually start with 'src/' — the
    prefix check alone is not sufficient, the '..' check must run too."""
    assert "src/../../../etc/passwd".startswith("src/")
    with pytest.raises(ValueError):
        source_to_test_path("src/../../../etc/passwd", _CONFIG)


def test_resolve_contained_source_path_accepts_normal_file(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "foo.py").write_text("x = 1\n")
    resolved = resolve_contained_source_path(tmp_path, "src/foo.py")
    assert resolved == (tmp_path / "src" / "foo.py").resolve()


def test_resolve_contained_source_path_rejects_traversal_outside_repo_root(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="resolves outside repo_root"):
        resolve_contained_source_path(tmp_path, "src/../../../etc/passwd")


def test_resolve_contained_source_path_rejects_absolute_path_escape(
    tmp_path: Path,
) -> None:
    """An absolute path passed as source_file — Path's / operator treats an
    absolute right-hand operand as a full replacement, not a join, so this
    must also be caught."""
    with pytest.raises(ValueError, match="resolves outside repo_root"):
        resolve_contained_source_path(tmp_path, "/etc/passwd")


def test_resolve_contained_source_path_never_touches_filesystem_for_rejected_paths(
    tmp_path: Path,
) -> None:
    """The containment check must run before any exists()/is_file() probe —
    the whole point is not leaking existence information about paths outside
    the repo via error-message differences."""
    with pytest.raises(ValueError):
        resolve_contained_source_path(tmp_path, "../../../../../../etc/shadow")
