# src/shared/infrastructure/intent/machinery_floor_integrity.py
"""
Machinery-floor integrity: is a target's ``.intent/`` carrying CORE's shipped
floor byte-for-byte? (ADR-159 Note 2026-09-15, #894 Condition 1.)

Under one Mind per process, the bound target's ``.intent/`` is the ONLY law
the process reads -- including the machinery law CORE ships as the floor
(``src/shared/_machinery_floor``). An overlay that could edit a floor file
could therefore demote machinery risk, which under ADR-160 only the
Governor may do. Condition 1: every floor file in the target must be
byte-identical to the shipped floor, or the run refuses; the overlay is
additive-only.

Floor hash set (Condition 1 as ruled): every file under the shipped floor
except ``__pycache__/`` -- the ``__init__.py`` package markers ship with
the floor and ARE floor content, verified like any other file. Excluding
a file class would create an unverified slot inside ``.intent/``.

Pure functions over explicit paths. No ``get_intent_repository()`` import,
directly or transitively -- these checks run BEFORE bootstrap, when the
global IntentRepository singleton must not yet exist (same constraint as
``external_target_binding.py``; see its module docstring). The floor root
comes from ``importlib.resources`` (as ``_floor.resolve_floor_path`` does)
so this works from an installed wheel, not only a source checkout.
"""

from __future__ import annotations

import hashlib
import importlib.resources
from dataclasses import dataclass, field
from pathlib import Path


_FLOOR_PACKAGE = "shared._machinery_floor"
_EXCLUDED_DIRS = frozenset({"__pycache__"})


def _floor_root() -> Path:
    return Path(str(importlib.resources.files(_FLOOR_PACKAGE)))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_floor_files(root: Path) -> list[Path]:
    return sorted(
        p
        for p in root.rglob("*")
        if p.is_file() and not (_EXCLUDED_DIRS & set(p.relative_to(root).parts))
    )


@dataclass(frozen=True)
# ID: 9f816b13-49c7-4b91-9237-2ec67161925f
class FloorIntegrityReport:
    """Outcome of :func:`verify_floor` for one target ``.intent/``.

    ``ok`` / ``modified`` / ``missing`` are floor-relative POSIX paths
    (e.g. ``META/enums.json``). The report is clean iff both ``modified``
    and ``missing`` are empty; every floor file then appears in ``ok``.
    """

    ok: tuple[str, ...] = field(default_factory=tuple)
    modified: tuple[str, ...] = field(default_factory=tuple)
    missing: tuple[str, ...] = field(default_factory=tuple)

    @property
    # ID: 7f396b49-61d0-4686-a407-0239cb37fa41
    def clean(self) -> bool:
        return not self.modified and not self.missing

    # ID: 0cc859d9-4655-45f6-8ea7-5260ecdea1ee
    def describe(self) -> str:
        """Human-readable summary, safe to print in a refusal message."""
        parts = [
            f"floor files: {len(self.ok) + len(self.modified) + len(self.missing)}"
        ]
        if self.modified:
            parts.append(f"modified: {', '.join(self.modified)}")
        if self.missing:
            parts.append(f"missing: {', '.join(self.missing)}")
        if self.clean:
            parts.append("all byte-identical to the shipped floor")
        return "; ".join(parts)


# ID: 7fd125e0-81b9-41ea-a670-478414b9b167
def floor_manifest() -> dict[str, str]:
    """Return ``{floor_relative_posix_path: sha256}`` for every shipped floor file.

    Derived from the packaged floor at call time -- never hardcode the
    count; the set is whatever ships.
    """
    root = _floor_root()
    return {
        p.relative_to(root).as_posix(): _sha256_file(p) for p in _iter_floor_files(root)
    }


# ID: 589cbb1e-adc6-4b4b-a7dc-97fefd6c38ad
def floor_hash() -> str:
    """One SHA-256 over the sorted ``(relative_path, file_hash)`` list.

    Recorded in a run's identity so the export can state which floor the
    run was bound to.
    """
    h = hashlib.sha256()
    for rel, digest in sorted(floor_manifest().items()):
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(digest.encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


# ID: c09e6164-bcb5-4b95-94b7-0a43718e40a5
def verify_floor(intent_root: Path) -> FloorIntegrityReport:
    """Compare every shipped floor file against *intent_root* (a target's ``.intent/``).

    A floor path absent from the target is ``missing``; present with
    different bytes is ``modified``; byte-identical is ``ok``. Files the
    target carries that are not floor paths (the overlay) are not
    examined -- the overlay is free to add.
    """
    intent_root = Path(intent_root)
    ok: list[str] = []
    modified: list[str] = []
    missing: list[str] = []
    for rel, digest in sorted(floor_manifest().items()):
        candidate = intent_root / rel
        if not candidate.is_file():
            missing.append(rel)
        elif _sha256_file(candidate) != digest:
            modified.append(rel)
        else:
            ok.append(rel)
    return FloorIntegrityReport(
        ok=tuple(ok), modified=tuple(modified), missing=tuple(missing)
    )


# ID: baf28b9e-2d9f-4b33-98f1-224b53829f21
def find_collisions(subject_intent_root: Path) -> list[str]:
    """Floor paths that exist in a subject's ``.intent/`` with DIFFERENT bytes (D-e).

    Used before materializing a copy: a byte-identical file is not a
    collision (the floor would overwrite it with itself); an absent file is
    not a collision (materialization adds it). Only a differing file is --
    materializing would replace the subject's bytes, which the run must
    refuse rather than overwrite, skip, or merge. A subject with no
    ``.intent/`` at all has no collisions.
    """
    subject_intent_root = Path(subject_intent_root)
    if not subject_intent_root.is_dir():
        return []
    report = verify_floor(subject_intent_root)
    return list(report.modified)
