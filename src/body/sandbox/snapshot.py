# src/body/sandbox/snapshot.py
"""
Race-safe snapshot of a tree for a sandbox job (ADR-132 D10.10).

The sandbox never reads a tree on disk; it reads a copy the client makes
into an inbox directory. This module reads that copy's content:

- The walk uses directory descriptors only. Each entry is opened with
  ``O_NOFOLLOW`` relative to its parent's descriptor, and its type is decided
  by ``fstat`` on what was opened, never by an earlier ``stat``. A symlink
  (``ELOOP`` on open) is recorded as a link with its link text; its target is
  never read. So the copy holds no bytes reached through a link.
- Only an allow-listed set of top-level paths is read. Inside them, a name
  that looks like a secret (``.env*``, ``.secrets``) or repository metadata
  (``.git``, ``.venv``) refuses the whole snapshot; caches are skipped.
- Anything that is not a regular file, directory or symlink refuses the
  whole snapshot. Counts and sizes are capped.

The digest covers every entry (path, kind, content or link text), so a
result can be bound to exactly what ran.

CONSTITUTIONAL ALIGNMENT:
- Read-only. Writing the copy goes through FileHandler.write_snapshot.
"""

from __future__ import annotations

import errno
import hashlib
import os
import stat
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


EntryKind = Literal["dir", "file", "link"]

DEFAULT_INCLUDE: tuple[str, ...] = ("src", "tests", "pyproject.toml")
LAW_NAMES: tuple[str, ...] = (".intent", ".specs")
MAX_ENTRIES = 50_000
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024

SKIPPED_NAMES = frozenset(
    {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
)
_REFUSED_NAMES = frozenset({".git", ".venv", ".secrets"})
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC


# ID: 4f8180ef-f992-430a-ae0c-00fd0c8a7151
class SnapshotRefused(ValueError):
    """The tree cannot be copied safely; nothing is copied and nothing runs."""


@dataclass(frozen=True)
# ID: 3392cfd5-2041-4bbb-8218-ce4beafa3f40
class SnapshotEntry:
    """One entry of a snapshot. ``data`` is file bytes or link text."""

    rel_path: str
    kind: EntryKind
    data: bytes = b""


# ID: a91a41f4-d761-4608-ab58-0d795e81d873
def is_refused_name(name: str) -> bool:
    """A name the snapshot must never carry: secrets and repository metadata."""
    return name in _REFUSED_NAMES or name == ".env" or name.startswith(".env.")


# ID: f155ff6b-7940-457f-a12d-a110b4a9a842
def read_snapshot(
    tree_root: Path,
    include: tuple[str, ...] = DEFAULT_INCLUDE,
    law: tuple[Path, ...] = (),
) -> list[SnapshotEntry]:
    """Read the allow-listed part of *tree_root*, refusing anything unsafe.

    A top-level name in *include* that does not exist is skipped (a tree may
    have no ``tests/``). Raises ``SnapshotRefused`` on any unsafe entry.

    *law* names law roots (``.intent``, ``.specs``) to copy in at the top
    level under their own names. Under D2 the law is kept beside the clone,
    and the sandbox cannot read it there; the tests read it, and it is
    public text. A law root replaces a same-named entry of the tree.
    """
    for name in include:
        parts = name.split("/")
        if (
            not name
            or name.startswith("/")
            or any(p in ("", ".", "..") or is_refused_name(p) for p in parts)
        ):
            raise SnapshotRefused(f"include must be relative names: {name!r}")
    for root in law:
        if root.name not in LAW_NAMES:
            raise SnapshotRefused(f"law roots must be named {LAW_NAMES}: {root}")
    law_names = {root.name for root in law}
    try:
        root_fd = os.open(tree_root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    except OSError as exc:
        raise SnapshotRefused(f"tree root cannot be opened: {exc}") from exc
    entries: list[SnapshotEntry] = []
    budget = _Budget()
    try:
        seen_dirs: set[str] = set()
        for name in sorted(set(include) - law_names):
            for entry in _read_included(root_fd, name, budget):
                if entry.kind == "dir":
                    if entry.rel_path in seen_dirs:
                        continue  # a parent shared by two nested includes
                    seen_dirs.add(entry.rel_path)
                entries.append(entry)
    finally:
        os.close(root_fd)
    for root in law:
        try:
            parent_fd = os.open(
                root.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
            )
        except OSError as exc:
            raise SnapshotRefused(f"law root cannot be opened: {exc}") from exc
        try:
            entries.extend(_read_entry(parent_fd, root.name, root.name, budget))
        finally:
            os.close(parent_fd)
    return entries


# ID: 7c636e87-6c0f-4e14-be44-1dc4c016e6f5
def snapshot_digest(entries: list[SnapshotEntry]) -> str:
    """sha256 over every entry's path, kind and content (link text for links)."""
    digest = hashlib.sha256()
    for entry in sorted(entries, key=lambda e: e.rel_path):
        digest.update(entry.kind.encode())
        digest.update(b"\0")
        digest.update(entry.rel_path.encode("utf-8", "surrogateescape"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(entry.data).digest())
    return digest.hexdigest()


class _Budget:
    def __init__(self) -> None:
        self.entries = 0
        self.total_bytes = 0

    # ID: a30b2882-7cc4-4698-b84b-048b5da692dc
    def charge(self, rel_path: str, size: int) -> None:
        self.entries += 1
        self.total_bytes += size
        if self.entries > MAX_ENTRIES:
            raise SnapshotRefused(f"more than {MAX_ENTRIES} entries")
        if size > MAX_FILE_BYTES:
            raise SnapshotRefused(f"{rel_path} is larger than {MAX_FILE_BYTES} bytes")
        if self.total_bytes > MAX_TOTAL_BYTES:
            raise SnapshotRefused(f"snapshot larger than {MAX_TOTAL_BYTES} bytes")


def _read_included(root_fd: int, name: str, budget: _Budget) -> list[SnapshotEntry]:
    """An include, top-level or nested (``var/prompts``): its parent directories
    are recorded as directories and opened without following links."""
    *parents, leaf = name.split("/")
    entries: list[SnapshotEntry] = []
    fds: list[int] = []
    try:
        fd = root_fd
        for i, part in enumerate(parents):
            try:
                fd = os.open(part, _DIR_FLAGS, dir_fd=fd)
            except FileNotFoundError:
                return []  # an allow-listed path the tree does not have
            except OSError as exc:
                raise SnapshotRefused(f"{name} cannot be opened: {exc}") from exc
            fds.append(fd)
            entries.append(SnapshotEntry("/".join(parents[: i + 1]), "dir"))
        if parents:
            try:
                os.stat(leaf, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                return []  # an allow-listed path the tree does not have
        return entries + list(_read_entry(fd, leaf, name, budget))
    finally:
        for opened in fds:
            os.close(opened)


def _read_entry(
    parent_fd: int, name: str, rel_path: str, budget: _Budget
) -> Iterator[SnapshotEntry]:
    if is_refused_name(name):
        raise SnapshotRefused(f"refused name in snapshot: {rel_path}")
    if name in SKIPPED_NAMES:
        return
    try:
        fd = os.open(name, _FILE_FLAGS, dir_fd=parent_fd)
    except FileNotFoundError:
        if "/" not in rel_path:
            return  # an allow-listed top-level name the tree does not have
        raise SnapshotRefused(f"{rel_path} vanished during the walk") from None
    except OSError as exc:
        if exc.errno != errno.ELOOP:
            raise SnapshotRefused(f"{rel_path} cannot be opened: {exc}") from exc
        yield _read_link(parent_fd, name, rel_path, budget)
        return
    try:
        mode = os.fstat(fd).st_mode
        if stat.S_ISREG(mode):
            yield _read_file(fd, rel_path, budget)
        elif stat.S_ISDIR(mode):
            yield from _read_dir(fd, rel_path, budget)
        else:
            raise SnapshotRefused(f"{rel_path} is not a regular file or directory")
    finally:
        os.close(fd)


def _read_link(
    parent_fd: int, name: str, rel_path: str, budget: _Budget
) -> SnapshotEntry:
    try:
        target = os.readlink(name, dir_fd=parent_fd)
    except OSError as exc:
        raise SnapshotRefused(f"{rel_path} changed during the walk: {exc}") from exc
    data = os.fsencode(target)
    budget.charge(rel_path, len(data))
    return SnapshotEntry(rel_path=rel_path, kind="link", data=data)


def _read_file(fd: int, rel_path: str, budget: _Budget) -> SnapshotEntry:
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_FILE_BYTES:
            raise SnapshotRefused(f"{rel_path} is larger than {MAX_FILE_BYTES} bytes")
        chunks.append(chunk)
    budget.charge(rel_path, size)
    return SnapshotEntry(rel_path=rel_path, kind="file", data=b"".join(chunks))


def _read_dir(fd: int, rel_path: str, budget: _Budget) -> Iterator[SnapshotEntry]:
    dir_fd = os.open(".", _DIR_FLAGS, dir_fd=fd)
    try:
        budget.charge(rel_path, 0)
        yield SnapshotEntry(rel_path=rel_path, kind="dir")
        for child in sorted(os.listdir(dir_fd)):
            yield from _read_entry(dir_fd, child, f"{rel_path}/{child}", budget)
    finally:
        os.close(dir_fd)
