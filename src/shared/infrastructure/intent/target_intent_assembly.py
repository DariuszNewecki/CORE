# src/shared/infrastructure/intent/target_intent_assembly.py
"""
Assemble a target's ``.intent/`` = shipped machinery floor + additive overlay
(ADR-159 Note 2026-09-15, #894 Condition 1 / D-b).

Two layers, in order:

1. the shipped machinery floor (``src/shared/_machinery_floor``), copied
   verbatim -- every file, ``__init__.py`` markers included, ``__pycache__``
   excluded (the same set :func:`machinery_floor_integrity.floor_manifest`
   verifies);
2. an overlay directory whose tree mirrors ``.intent/`` layout (e.g.
   ``rules/code/purity.json``, ``workers/<name>.yaml``,
   ``enforcement/config/safe_auto_approval_envelope.yaml``), copied
   additively. An overlay path that is also a floor path is REFUSED --
   never merged, never overwritten -- because under one Mind per process an
   overlay able to edit a floor file could demote machinery risk (ADR-160:
   only the Governor may). This is Condition 1 enforced at assembly, before
   :func:`machinery_floor_integrity.verify_floor` re-checks it at bind.

Productionized from ``tests/fixtures/external_target/materialize.py``
(Unit C) so the external-run command and the future offline onboard share
one builder; the fixture now calls this.

Writes: the destination is, by construction, OUTSIDE any repository CORE is
bound to (an evidence-root run directory, or a pytest ``tmp_path``), so
``FileHandler``'s repo-relative path guards cannot classify it -- the same
situation ADR-147 D4 records for ``canary_janitor``. Copies use ``shutil``
directly for that reason and for no other; nothing here writes inside
``REPO_PATH`` or CORE's own checkout. No ``get_intent_repository()``
import, directly or transitively (pre-bootstrap constraint; see
``external_target_binding.py``).
"""

from __future__ import annotations

import hashlib
import importlib.resources
import shutil
from dataclasses import dataclass
from pathlib import Path

from shared.exceptions import CoreError
from shared.infrastructure.intent.machinery_floor_integrity import (
    floor_hash,
    floor_manifest,
)


_FLOOR_PACKAGE = "shared._machinery_floor"
_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")


# ID: 65462650-2b8e-44e7-8054-16691839a74a
class OverlayCollisionError(CoreError):
    """The overlay names a path the floor owns (Condition 1: additive-only)."""


# ID: aa4ba13d-05a1-4186-9a08-bd4bc884498f
@dataclass(frozen=True)
class AssembledIntent:
    """What :func:`assemble_target_intent` produced."""

    intent_root: Path
    floor_hash: str
    overlay_hash: str
    overlay_files: tuple[str, ...]


def _overlay_files(overlay_dir: Path) -> list[Path]:
    return sorted(
        p
        for p in overlay_dir.rglob("*")
        if p.is_file()
        and "__pycache__" not in p.relative_to(overlay_dir).parts
        and p.suffix != ".pyc"
    )


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ID: 32ef16e2-01d5-4f75-ae23-06f45c352f2e
def overlay_hash(overlay_dir: Path | None) -> str:
    """One SHA-256 over the overlay's sorted ``(relative_path, file_hash)`` list.

    Recorded in a run's identity alongside the floor hash (Condition 2).
    ``None``, an absent or an empty overlay all hash to the empty list's digest.
    """
    h = hashlib.sha256()
    if overlay_dir is not None and Path(overlay_dir).is_dir():
        overlay_dir = Path(overlay_dir)
        for p in _overlay_files(overlay_dir):
            h.update(p.relative_to(overlay_dir).as_posix().encode("utf-8"))
            h.update(b"\0")
            h.update(_sha256_file(p).encode("ascii"))
            h.update(b"\n")
    return h.hexdigest()


# ID: 68ad743c-9582-4600-9973-1ef4e628b109
def assemble_target_intent(
    intent_root: Path, overlay_dir: Path | None = None
) -> AssembledIntent:
    """Create *intent_root* as floor + overlay. *intent_root* must not exist.

    Raises :class:`OverlayCollisionError` -- before writing anything -- if
    the overlay names any floor path. Raises ``FileExistsError`` if
    *intent_root* already exists: this builder never merges into an
    existing ``.intent/``.
    """
    intent_root = Path(intent_root)
    if intent_root.exists():
        raise FileExistsError(
            f"refusing to assemble into an existing path: {intent_root}"
        )

    manifest = floor_manifest()
    overlay_paths: list[Path] = []
    if overlay_dir is not None:
        overlay_dir = Path(overlay_dir)
        if not overlay_dir.is_dir():
            raise OverlayCollisionError(f"overlay directory not found: {overlay_dir}")
        overlay_paths = _overlay_files(overlay_dir)
        collisions = [
            p.relative_to(overlay_dir).as_posix()
            for p in overlay_paths
            if p.relative_to(overlay_dir).as_posix() in manifest
        ]
        if collisions:
            raise OverlayCollisionError(
                "overlay may not modify floor files (Condition 1, additive-only): "
                + ", ".join(collisions)
            )

    floor_root = Path(str(importlib.resources.files(_FLOOR_PACKAGE)))
    shutil.copytree(floor_root, intent_root, ignore=_IGNORE)

    written: list[str] = []
    for src in overlay_paths:
        rel = src.relative_to(overlay_dir)  # type: ignore[arg-type]
        dest = intent_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        written.append(rel.as_posix())

    return AssembledIntent(
        intent_root=intent_root,
        floor_hash=floor_hash(),
        overlay_hash=overlay_hash(overlay_dir),
        overlay_files=tuple(written),
    )
