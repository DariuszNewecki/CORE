# tests/body/sandbox/test_snapshot.py
"""Race-safe snapshot reading and writing (ADR-132 D10.10)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from body.infrastructure.storage.file_handler import FileHandler
from body.sandbox import snapshot as snap
from body.sandbox.snapshot import SnapshotRefused, read_snapshot, snapshot_digest
from shared.exceptions import RepositoryBoundaryViolationError


def _tree(root: Path) -> Path:
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "pkg" / "__init__.py").write_text("X = 1\n")
    (root / "tests").mkdir()
    (root / "tests" / "test_a.py").write_text("def test_a():\n    pass\n")
    (root / "pyproject.toml").write_text("[project]\n")
    (root / "var").mkdir()
    (root / "var" / "big.log").write_text("not copied\n")
    return root


def test_reads_only_the_allow_list(scratch: Path) -> None:
    entries = read_snapshot(_tree(scratch / "t"))
    paths = {e.rel_path for e in entries}
    assert "src/pkg/__init__.py" in paths
    assert "tests/test_a.py" in paths
    assert "pyproject.toml" in paths
    assert not any(p.startswith("var") for p in paths)


def test_missing_top_level_name_is_skipped(scratch: Path) -> None:
    root = scratch / "t"
    (root / "src").mkdir(parents=True)
    assert {e.rel_path for e in read_snapshot(root)} == {"src"}


@pytest.mark.parametrize("name", [".env", ".env.local", ".secrets", ".git", ".venv"])
def test_secret_and_metadata_names_refuse_the_snapshot(
    scratch: Path, name: str
) -> None:
    root = _tree(scratch / "t")
    target = root / "src" / name
    if name in (".secrets", ".git", ".venv"):
        target.mkdir()
    else:
        target.write_text("DATABASE_URL=postgres://secret\n")
    with pytest.raises(SnapshotRefused):
        read_snapshot(root)


def test_fifo_refuses_the_snapshot(scratch: Path) -> None:
    root = _tree(scratch / "t")
    os.mkfifo(root / "tests" / "pipe")
    with pytest.raises(SnapshotRefused):
        read_snapshot(root)


def test_symlink_is_recorded_as_link_text_never_followed(scratch: Path) -> None:
    root = _tree(scratch / "t")
    secret = scratch / "secret.env"
    secret.write_text("TOP-SECRET-BYTES\n")
    (root / "tests" / "leak").symlink_to(secret)
    entries = {e.rel_path: e for e in read_snapshot(root)}
    link = entries["tests/leak"]
    assert link.kind == "link"
    assert link.data == os.fsencode(str(secret))
    assert not any(b"TOP-SECRET" in e.data for e in entries.values())


def test_file_swapped_for_symlink_mid_walk_is_read_as_link(
    scratch: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _tree(scratch / "t")
    secret = scratch / "secret.env"
    secret.write_text("TOP-SECRET-BYTES\n")
    victim = root / "tests" / "test_a.py"
    real_listdir = os.listdir

    def racing_listdir(fd: int) -> list[str]:
        names = real_listdir(fd)
        if "test_a.py" in names and victim.is_file() and not victim.is_symlink():
            victim.unlink()
            victim.symlink_to(secret)  # swapped after listing, before open
        return names

    monkeypatch.setattr(snap.os, "listdir", racing_listdir)
    entries = {e.rel_path: e for e in read_snapshot(root)}
    assert entries["tests/test_a.py"].kind == "link"
    assert not any(b"TOP-SECRET" in e.data for e in entries.values())


def test_digest_tracks_content(scratch: Path) -> None:
    root = _tree(scratch / "t")
    first = snapshot_digest(read_snapshot(root))
    assert first == snapshot_digest(read_snapshot(root))
    (root / "src" / "pkg" / "__init__.py").write_text("X = 2\n")
    assert snapshot_digest(read_snapshot(root)) != first


def test_write_snapshot_recreates_files_dirs_and_links(
    scratch: Path, fh: FileHandler
) -> None:
    root = _tree(scratch / "t")
    (root / "tests" / "link").symlink_to("test_a.py")
    entries = read_snapshot(root)
    fh.write_snapshot("var/tmp/inbox/job", entries)
    out = fh.repo_path / "var/tmp/inbox/job"
    assert (out / "src/pkg/__init__.py").read_text() == "X = 1\n"
    assert (out / "tests/link").is_symlink()
    assert os.readlink(out / "tests/link") == "test_a.py"
    assert (out / "tests/test_a.py").stat().st_mode & 0o777 == 0o640
    assert (out / "tests").stat().st_mode & 0o777 == 0o750


def test_write_snapshot_refuses_an_existing_directory(fh: FileHandler) -> None:
    (fh.repo_path / "var/tmp/inbox/job").mkdir(parents=True)
    with pytest.raises(FileExistsError):
        fh.write_snapshot("var/tmp/inbox/job", [])


@pytest.mark.parametrize("bad", ["../escape", "/abs", "a/../../b", "a//b"])
def test_write_snapshot_refuses_escaping_entries(fh: FileHandler, bad: str) -> None:
    entry = snap.SnapshotEntry(rel_path=bad, kind="file", data=b"x")
    with pytest.raises(RepositoryBoundaryViolationError):
        fh.write_snapshot("var/tmp/inbox/job", [entry])
