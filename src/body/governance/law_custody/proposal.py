# src/body/governance/law_custody/proposal.py
"""
Read a law proposal into memory, once (ADR-170 D3 step 3.1).

A proposal is ``var/law-proposals/<id>/`` holding ``proposal.md`` and the
complete new files under ``files/``, mirroring repository paths. Everything
``law apply`` checks, shows and writes comes from the snapshot returned
here; the folder is never read again, so editing it afterwards changes
nothing (ADR-170 acceptance check 7).

``proposal.md`` sections read here:
- ``## Remove`` -- one ``- `path``` bullet per file to delete;
- ``## Declared warnings`` -- the proposer's meaning-level warnings
  (ADR-170 amendment 2026-10-11 (later), item 2), shown verbatim.

CONSTITUTIONAL ALIGNMENT:
- Read-only; no writes, no repository code executed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from shared.infrastructure.intent.governed_text import governed_paths_touched


_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_HEADING = re.compile(r"^#{2,}\s+(.*?)\s*$")
_ITEM = re.compile(r"^(?:[-*]|\d+[.)])\s+(.*)$")
_BACKTICK_PATH = re.compile(r"`([^`]+)`")


# ID: 93268a26-2ca0-4b4f-afcf-a24fe4ee6f55
class ProposalError(Exception):
    """The proposal cannot be read as a valid proposal; nothing is written."""


@dataclass(frozen=True)
# ID: c6f71960-4092-446a-8608-ee37bc824a97
class ProposedFile:
    """One complete new file, as bytes held in memory."""

    path: str
    content: bytes
    sha256: str


@dataclass(frozen=True)
# ID: 483382ef-2b12-40b6-a648-34d63621df17
class LawProposal:
    """A proposal snapshot. ``digest`` covers every path, hash and removal."""

    proposal_id: str
    files: tuple[ProposedFile, ...]
    removals: tuple[str, ...]
    proposal_md: str
    declared_warnings: tuple[str, ...]
    digest: str

    # ID: c3aaf317-7fbf-4a75-a517-a2edbf165afb
    def paths(self) -> list[str]:
        """Every path the proposal writes or removes, sorted."""
        return sorted([f.path for f in self.files] + list(self.removals))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sections(markdown: str) -> dict[str, list[str]]:
    """Map each heading's text (lower-cased) to the lines beneath it."""
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in markdown.splitlines():
        match = _HEADING.match(line)
        if match:
            current = sections.setdefault(match.group(1).strip().lower(), [])
            continue
        if current is not None:
            current.append(line)
    return sections


def _section(sections: dict[str, list[str]], name: str) -> list[str] | None:
    for heading, lines in sections.items():
        if name in heading:
            return lines
    return None


def _items(lines: list[str]) -> list[str]:
    """List items of a section; indented lines continue the previous item."""
    items: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        match = _ITEM.match(stripped)
        if match and not raw.startswith((" ", "\t")):
            items.append(match.group(1).strip())
        elif items and raw.startswith((" ", "\t")):
            items[-1] = f"{items[-1]} {stripped}"
    return items


# ID: 2c7e5303-605d-4703-9f9d-e20b929644a4
def parse_declared_warnings(proposal_md: str) -> tuple[str, ...]:
    """The items under ``## Declared warnings``, verbatim; empty if absent."""
    lines = _section(_sections(proposal_md), "declared warnings")
    return tuple(_items(lines)) if lines else ()


# ID: 928c325d-fe0b-49d5-ae56-6cfc6a65ef59
def parse_removals(proposal_md: str) -> tuple[str, ...]:
    """The paths under ``## Remove`` (one backticked path per item)."""
    lines = _section(_sections(proposal_md), "remove")
    if not lines:
        return ()
    paths: list[str] = []
    for item in _items(lines):
        match = _BACKTICK_PATH.search(item)
        if not match:
            raise ProposalError(f"'## Remove' item without a backticked path: {item!r}")
        paths.append(match.group(1).strip())
    return tuple(paths)


def _check_relpath(rel: str, governed: tuple[str, ...]) -> None:
    parts = Path(rel).parts
    if not rel or rel.startswith("/") or ".." in parts or "." in parts:
        raise ProposalError(f"not a plain repository-relative path: {rel!r}")
    if not governed_paths_touched([rel], governed):
        raise ProposalError(
            f"{rel} is not governed text; law apply writes governed text only"
        )


def _read_regular(path: Path) -> bytes:
    """Read *path*, refusing anything but a regular file (no symlinks)."""
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode):
        raise ProposalError(f"not a regular file (symlink or special): {path}")
    return path.read_bytes()


# ID: 0cc7e2ce-b520-41d8-901d-e45aeb82d62f
def read_proposal(
    proposals_dir: Path, proposal_id: str, governed: Iterable[str]
) -> LawProposal:
    """Read ``<proposals_dir>/<proposal_id>/`` into memory.

    Refuses (``ProposalError``) an id with a path separator, a missing
    ``proposal.md``, a symlink or special file anywhere under ``files/``,
    a path that is not governed text, a path both written and removed, and
    an empty proposal.
    """
    if not _ID_PATTERN.match(proposal_id):
        raise ProposalError(f"invalid proposal id: {proposal_id!r}")
    governed_entries = tuple(governed)
    root = proposals_dir / proposal_id
    if not root.is_dir() or root.is_symlink():
        raise ProposalError(f"no proposal folder: {root}")
    try:
        proposal_md = _read_regular(root / "proposal.md").decode("utf-8")
    except FileNotFoundError as exc:
        raise ProposalError(f"{root}/proposal.md is missing") from exc

    files: list[ProposedFile] = []
    files_root = root / "files"
    if files_root.exists():
        if files_root.is_symlink():
            raise ProposalError(f"{files_root} is a symlink")
        for dirpath, dirnames, filenames in os.walk(files_root):
            for name in dirnames:
                if (Path(dirpath) / name).is_symlink():
                    raise ProposalError(f"symlinked directory: {dirpath}/{name}")
            for name in filenames:
                full = Path(dirpath) / name
                rel = full.relative_to(files_root).as_posix()
                _check_relpath(rel, governed_entries)
                content = _read_regular(full)
                files.append(ProposedFile(rel, content, _sha256(content)))
    files.sort(key=lambda f: f.path)

    removals = parse_removals(proposal_md)
    for rel in removals:
        _check_relpath(rel, governed_entries)
    both = {f.path for f in files} & set(removals)
    if both:
        raise ProposalError(f"written and removed at once: {sorted(both)}")
    if not files and not removals:
        raise ProposalError("the proposal writes and removes nothing")

    digest = _sha256(
        json.dumps(
            {
                "files": [[f.path, f.sha256] for f in files],
                "removals": sorted(removals),
                "proposal_md": _sha256(proposal_md.encode("utf-8")),
            },
            sort_keys=True,
        ).encode("utf-8")
    )
    return LawProposal(
        proposal_id=proposal_id,
        files=tuple(files),
        removals=tuple(sorted(removals)),
        proposal_md=proposal_md,
        declared_warnings=parse_declared_warnings(proposal_md),
        digest=digest,
    )
