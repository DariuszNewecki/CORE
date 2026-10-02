"""Tests for ``shared.infrastructure.bundled_packs`` — repository first, bundle second."""

from __future__ import annotations

from pathlib import Path

from shared.infrastructure.bundled_packs import (
    bundled_packs_as_path,
    is_package_marker,
    pack_registry_dir,
)
from shared.infrastructure.intent.pack_loader import PackLoader


OPEN_PACKS = {
    "core/starter-python",
    "core/python-hygiene",
    "core/architectural-boundaries",
}


def test_repository_packs_dir_wins_when_present(tmp_path: Path) -> None:
    repo_packs = tmp_path / "packs"
    repo_packs.mkdir()
    with pack_registry_dir(tmp_path) as packs_dir:
        assert packs_dir == repo_packs


def test_bundle_used_when_repository_has_no_packs(tmp_path: Path) -> None:
    with pack_registry_dir(tmp_path) as packs_dir:
        assert packs_dir != tmp_path / "packs"
        ids = set(PackLoader(packs_dir).list_pack_ids())
    assert OPEN_PACKS <= ids


def test_bundled_packs_load_cleanly() -> None:
    with bundled_packs_as_path() as packs_dir:
        packs = PackLoader(packs_dir).load_all()
    assert {p.pack_id for p in packs} == OPEN_PACKS
    assert all(p.rules for p in packs)


def test_package_marker_is_not_payload() -> None:
    assert is_package_marker("__init__.py")
    assert not is_package_marker("starter_python.yaml")
