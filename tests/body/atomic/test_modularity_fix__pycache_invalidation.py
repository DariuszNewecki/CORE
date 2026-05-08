"""Regression test for issue #212: ``fix.modularity`` must invalidate stale
``.pyc`` artefacts after splitting a monolith into a package, so the daemon
does not serve old bytecode on restart.

The action's step 7 unlinks the original monolith. Without invalidation, the
runtime keeps the old ``foo.cpython-312.pyc`` in ``target.parent/__pycache__``
and a future daemon load may resolve imports against the deleted monolith
rather than the new package. Stale ``__pycache__`` under the new package
directory (e.g. left by a previous failed split) carries the same risk.

Documented as Failure 2 in ``.specs/papers/CORE-ModularityLessons.md``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from body.atomic.modularity_fix import _invalidate_split_pycache
from body.governance import intent_guard as _ig_module
from shared.infrastructure.storage.file_handler import FileHandler


_PY_TAG = f"cpython-{sys.version_info.major}{sys.version_info.minor}"


@pytest.fixture(autouse=True)
def _bypass_vocabulary_projection_check(monkeypatch):
    """Bypass IntentGuard's DEGRADED pre-check for the vocabulary projection.

    IntentGuard.check_transaction unconditionally calls
    ``load_vocabulary_projection(self.repo_path)`` and treats a
    ``VocabularyProjectionError`` as cause to block all writes. When
    FileHandler is constructed against a tempdir, the guard's bound repo_path
    is that tempdir — which has no ``.intent/META/vocabulary.json``, so the
    pre-check fires and blocks the test's legitimate ``__pycache__`` removal.

    The unit under test (``_invalidate_split_pycache``) is not exercising
    governance, so we patch the projection loader to return a non-error
    sentinel. The reset of the IntentGuard singleton ensures the patch takes
    effect on a freshly-constructed guard, not a stale cached one.
    """
    from unittest.mock import Mock

    _ig_module._INTENT_GUARD = None
    monkeypatch.setattr(
        "body.governance.intent_guard.load_vocabulary_projection",
        lambda *args, **kwargs: Mock(),
    )
    yield
    _ig_module._INTENT_GUARD = None


# ID: be3c686e-8c64-4372-9d51-38f0a3d58bd0
def test_invalidates_monolith_pyc_in_parent_pycache(tmp_path: Path) -> None:
    """Stale .pyc for the deleted monolith is removed; sibling .pyc untouched."""
    fh = FileHandler(str(tmp_path))

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    monolith = src_dir / "fat_module.py"
    monolith.write_text("# placeholder\n")

    pycache = src_dir / "__pycache__"
    pycache.mkdir()
    stale_pyc = pycache / f"fat_module.{_PY_TAG}.pyc"
    stale_pyc.write_bytes(b"stale bytecode")

    sibling_pyc = pycache / f"sibling.{_PY_TAG}.pyc"
    sibling_pyc.write_bytes(b"sibling bytecode")

    removed = _invalidate_split_pycache(monolith, fh, tmp_path)

    assert not stale_pyc.exists(), "monolith's stale .pyc should be removed"
    assert sibling_pyc.exists(), "sibling .pyc must not be touched"
    assert stale_pyc in removed


# ID: b8f90a41-9945-4d08-b1a7-2a394dd6c79c
def test_invalidates_nested_pycache_in_new_package_dir(tmp_path: Path) -> None:
    """__pycache__ directories under the new package are wiped recursively;
    package source files and __init__.py remain intact.
    """
    fh = FileHandler(str(tmp_path))

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    monolith = src_dir / "fat_module.py"
    monolith.write_text("# placeholder\n")

    pkg_dir = src_dir / "fat_module"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("\n")

    nested_pycache = pkg_dir / "__pycache__"
    nested_pycache.mkdir()
    (nested_pycache / "old.pyc").write_bytes(b"stale")

    sub_pkg = pkg_dir / "sub"
    sub_pkg.mkdir()
    (sub_pkg / "__init__.py").write_text("\n")
    deeper_pycache = sub_pkg / "__pycache__"
    deeper_pycache.mkdir()
    (deeper_pycache / "older.pyc").write_bytes(b"older")

    removed = _invalidate_split_pycache(monolith, fh, tmp_path)

    assert not nested_pycache.exists()
    assert not deeper_pycache.exists()
    assert pkg_dir.is_dir()
    assert (pkg_dir / "__init__.py").exists()
    assert sub_pkg.is_dir()
    assert (sub_pkg / "__init__.py").exists()
    assert nested_pycache in removed
    assert deeper_pycache in removed


# ID: 5399d8da-8e2d-4365-8665-95ecf9ec8968
def test_no_op_when_no_stale_artefacts_present(tmp_path: Path) -> None:
    """Helper returns an empty list and does not raise when there is nothing
    to invalidate. Important because step 7 calls it unconditionally.
    """
    fh = FileHandler(str(tmp_path))

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    monolith = src_dir / "fat_module.py"
    monolith.write_text("# placeholder\n")

    removed = _invalidate_split_pycache(monolith, fh, tmp_path)
    assert removed == []
