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

A second entry point, :func:`materialize_execution_copy`, builds the
**execution copy** of a frozen subject for an external run (Condition 2 +
the collision rule, ADR-159 Note 2026-09-15): the subject tree is copied
(symlinks preserved, never dereferenced; only the subject root's ``.git``
excluded), then its ``.intent/`` is reconciled with the floor -- on
collision the framework-owned floor replaces the subject's floor file, the
displaced original is preserved byte-for-byte under the run's evidence
tree, and a deterministic manifest records path, original hash and
installed-floor hash. The frozen subject is never written to. An overlay
path that collides with a subject's NON-floor file is refused: no ruling
chooses a winner there, and silently replacing subject law would breach
the additive-only boundary.

Writes: the authority for writing here at all is ADR-159's materialized-
copy ruling (Note 2026-09-15, Condition 2): the destination is, by
construction, OUTSIDE any repository CORE is bound to -- an evidence-root
run directory, or a pytest ``tmp_path``. ``FileHandler`` is repo-bound and
cannot classify such a location (ADR-147 D4 and ADR-155 record the same
limitation for ``work/`` and the demo state dir; they are precedent for
the limitation, not the authority for this write). Copies therefore use
``shutil`` directly; nothing here writes inside ``REPO_PATH`` or CORE's
own checkout. No ``get_intent_repository()`` import, directly or
transitively (pre-bootstrap constraint; see ``external_target_binding.py``).
"""

from __future__ import annotations

import hashlib
import importlib.resources
import json
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.exceptions import CoreError
from shared.infrastructure.intent.machinery_floor_integrity import (
    floor_hash,
    floor_manifest,
    verify_floor,
)


_FLOOR_PACKAGE = "shared._machinery_floor"
_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")


# ID: 65462650-2b8e-44e7-8054-16691839a74a
class OverlayCollisionError(CoreError):
    """The overlay names a path the floor owns (Condition 1: additive-only)."""


@dataclass(frozen=True)
# ID: af36b8d6-aaf4-481e-b2d3-323fb60c9caf
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


# ID: ab88a4be-1ab2-460e-8d5c-8ed9467ee81b
class SubjectCopyError(CoreError):
    """The subject cannot be copied faithfully (unsupported special file,
    a non-regular file at a floor path, or an overlay/subject collision)."""


@dataclass(frozen=True)
# ID: ffdf71d7-40f6-4c0a-93a3-f03916fb3bf5
class DisplacedFloorFile:
    """One subject floor file the floor replaced in the execution copy."""

    path: str
    original_sha256: str
    installed_floor_sha256: str


@dataclass(frozen=True)
# ID: 0ba83394-f776-4341-908a-e490db8a2b64
class InstalledPrompt:
    """One runner prompt artifact installed into the execution copy
    (ruling B: the planner prompt is runner machinery, not subject law)."""

    prompt_id: str
    files: dict[str, str]  # filename -> sha256 of the installed (runner) bytes
    displaced_original_sha256: dict[
        str, str
    ]  # filename -> subject's sha256, if displaced


@dataclass(frozen=True)
# ID: 81120df0-b4dc-419b-b384-607a7fd95460
class ExecutionCopy:
    """What :func:`materialize_execution_copy` produced."""

    target_root: Path
    intent_root: Path
    evidence_root: Path
    floor_hash: str
    overlay_hash: str
    overlay_files: tuple[str, ...]
    displaced: tuple[DisplacedFloorFile, ...]
    collision_manifest_path: Path
    prompts: tuple[InstalledPrompt, ...] = ()
    prompt_collision_manifest_path: Path | None = None


def _iter_tree(root: Path, *, skip_root_git: bool) -> list[Path]:
    """Every entry under *root* (files, symlinks, dirs), depth-first, sorted,
    via ``os.walk(followlinks=False)`` so symlinked directories are listed as
    the links they are and never descended into."""
    entries: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        d = Path(dirpath)
        if skip_root_git and d == root and ".git" in dirnames:
            dirnames.remove(".git")
        dirnames.sort()
        for name in sorted(dirnames):
            entries.append(d / name)
        for name in sorted(filenames):
            entries.append(d / name)
    return sorted(entries)


def _entry_kind(st: os.stat_result) -> str:
    mode = st.st_mode
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "dir"
    return "special"


# ID: 799071c5-86a0-4ffd-8cc5-2ce0efadf76d
def subject_fingerprint(subject_root: Path) -> str:
    """SHA-256 over every entry under *subject_root* except the root ``.git``.

    Each line: ``relative_path \0 kind \0 mode(octal) \0 content_hash``.
    Regular files hash their bytes; symlinks hash their link-target TEXT
    (``os.readlink``, taken via ``lstat`` -- the link is never followed, so
    a link pointing outside the subject contributes only its text);
    directories hash nothing. Mode is the full ``st_mode`` so a chmod
    (executable bit) changes the fingerprint. Raises
    :class:`SubjectCopyError` on any special file (socket, fifo, device),
    which the copy would not reproduce either.
    """
    subject_root = Path(subject_root)
    h = hashlib.sha256()
    for entry in _iter_tree(subject_root, skip_root_git=True):
        st = entry.lstat()
        kind = _entry_kind(st)
        rel = entry.relative_to(subject_root).as_posix()
        if kind == "special":
            raise SubjectCopyError(f"unsupported special file in subject: {rel}")
        if kind == "file":
            content = _sha256_file(entry)
        elif kind == "symlink":
            content = hashlib.sha256(
                os.readlink(entry).encode("utf-8", "surrogateescape")
            ).hexdigest()
        else:
            content = ""
        h.update(rel.encode("utf-8", "surrogateescape"))
        h.update(b"\0")
        h.update(kind.encode("ascii"))
        h.update(b"\0")
        h.update(oct(st.st_mode).encode("ascii"))
        h.update(b"\0")
        h.update(content.encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def _copy_subject_tree(subject_root: Path, dest: Path) -> None:
    """Copy *subject_root* to *dest* preserving symlinks (never dereferenced),
    modes and timestamps; only the subject root's ``.git`` is excluded.
    Refuses special files rather than silently dropping them."""
    for entry in _iter_tree(subject_root, skip_root_git=True):
        if _entry_kind(entry.lstat()) == "special":
            raise SubjectCopyError(
                f"unsupported special file in subject: {entry.relative_to(subject_root)}"
            )

    def _ignore_root_git(directory: str, names: list[str]) -> set[str]:
        return (
            {".git"} if Path(directory) == subject_root and ".git" in names else set()
        )

    shutil.copytree(
        subject_root,
        dest,
        symlinks=True,
        ignore=_ignore_root_git,
        copy_function=shutil.copy2,
    )


# ID: 749a6d78-985b-49d8-ab6f-2a423867b48f
def materialize_execution_copy(
    subject_root: Path,
    run_root: Path,
    overlay_dir: Path | None = None,
    *,
    prompt_sources: dict[str, Path] | None = None,
) -> ExecutionCopy:
    """Build ``<run_root>/target/`` (the execution copy) and ``<run_root>/evidence/``.

    Siblings by construction: CORE executes against ``target/`` and never
    against or through ``evidence/``. *run_root* must not exist. The frozen
    *subject_root* is only read.

    Floor reconciliation inside ``target/.intent/`` (creating it if the
    subject has none): for each shipped floor path -- absent: install the
    floor file; byte-identical: leave; different (a collision): move the
    subject's original to ``evidence/displaced/<path>``, install the floor
    file, and record ``(path, original_sha256, installed_floor_sha256)`` in
    ``evidence/collision_manifest.json`` (sorted by path, deterministic).
    A non-regular file (symlink, dir) at a floor path is refused. Then the
    overlay is applied additively; an overlay path that already exists in
    the copy's ``.intent/`` (a subject non-floor file) is refused.

    *prompt_sources* (ruling B, 2026-09-15): ``{prompt_id: <runner dir>}`` --
    runner prompt artifacts installed at ``target/var/prompts/<id>/``. The
    runner's prompt wins: a subject copy with different bytes is preserved
    byte-for-byte under ``evidence/displaced/var/prompts/<id>/`` and both
    hashes are recorded in ``evidence/prompt_collision_manifest.json``. A
    source directory that is missing or lacks ``model.yaml`` is refused --
    a partial prompt must never be installed.
    """
    subject_root = Path(subject_root).resolve()
    run_root = Path(run_root)
    if run_root.exists():
        raise FileExistsError(
            f"refusing to materialize into an existing path: {run_root}"
        )
    if overlay_dir is not None and not Path(overlay_dir).is_dir():
        raise OverlayCollisionError(f"overlay directory not found: {overlay_dir}")

    target_root = run_root / "target"
    evidence_root = run_root / "evidence"
    displaced_root = evidence_root / "displaced"
    evidence_root.mkdir(parents=True)
    _copy_subject_tree(subject_root, target_root)

    intent_root = target_root / ".intent"
    intent_root.mkdir(exist_ok=True)
    floor_root = Path(str(importlib.resources.files(_FLOOR_PACKAGE)))
    manifest = floor_manifest()

    displaced: list[DisplacedFloorFile] = []
    for rel, floor_digest in sorted(manifest.items()):
        dest = intent_root / rel
        src = floor_root / rel
        if dest.is_symlink() or (dest.exists() and not dest.is_file()):
            raise SubjectCopyError(
                f"non-regular file at floor path in subject .intent/: {rel}"
            )
        if dest.is_file():
            original_digest = _sha256_file(dest)
            if original_digest == floor_digest:
                continue
            keep = displaced_root / rel
            keep.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dest), str(keep))
            displaced.append(
                DisplacedFloorFile(
                    path=rel,
                    original_sha256=original_digest,
                    installed_floor_sha256=floor_digest,
                )
            )
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)

    written: list[str] = []
    if overlay_dir is not None:
        overlay_dir = Path(overlay_dir)
        overlay_paths = _overlay_files(overlay_dir)
        clashes = [
            p.relative_to(overlay_dir).as_posix()
            for p in overlay_paths
            if (intent_root / p.relative_to(overlay_dir)).exists()
        ]
        if clashes:
            raise OverlayCollisionError(
                "overlay collides with files already present in the copy's "
                ".intent/ (floor or subject law); no ruling chooses a winner: "
                + ", ".join(clashes)
            )
        for src_path in overlay_paths:
            rel_p = src_path.relative_to(overlay_dir)
            dest = intent_root / rel_p
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src_path, dest)
            written.append(rel_p.as_posix())

    installed_prompts: list[InstalledPrompt] = []
    prompt_manifest_path: Path | None = None
    if prompt_sources:
        # The prompt root is wherever the bound runtime will look for it --
        # PathResolver over the execution copy, never a literal.
        from shared.path_resolver import PathResolver

        prompts_root = PathResolver(target_root).prompts_dir
        prompts_rel = prompts_root.relative_to(target_root.resolve())
        displaced_prompts_root = displaced_root / prompts_rel
        prompt_records: list[dict[str, Any]] = []
        for prompt_id, source in sorted(prompt_sources.items()):
            source_dir = Path(source)
            if not source_dir.is_dir() or not (source_dir / "model.yaml").is_file():
                raise SubjectCopyError(
                    f"runner prompt {prompt_id!r} unavailable or partial at {source_dir}"
                )
            dest_dir = prompts_root / prompt_id
            if dest_dir.exists() and not dest_dir.is_dir():
                raise SubjectCopyError(
                    f"non-directory at subject prompt path {prompts_rel}/{prompt_id}"
                )
            dest_dir.mkdir(parents=True, exist_ok=True)
            files: dict[str, str] = {}
            displaced_hashes: dict[str, str] = {}
            for src_file in sorted(p for p in source_dir.iterdir() if p.is_file()):
                dest_file = dest_dir / src_file.name
                runner_digest = _sha256_file(src_file)
                if dest_file.is_symlink() or (
                    dest_file.exists() and not dest_file.is_file()
                ):
                    raise SubjectCopyError(
                        "non-regular file at subject prompt path "
                        f"{prompts_rel}/{prompt_id}/{src_file.name}"
                    )
                if dest_file.is_file():
                    original_digest = _sha256_file(dest_file)
                    if original_digest == runner_digest:
                        files[src_file.name] = runner_digest
                        continue
                    keep = displaced_prompts_root / prompt_id / src_file.name
                    keep.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(dest_file), str(keep))
                    displaced_hashes[src_file.name] = original_digest
                shutil.copyfile(src_file, dest_file)
                files[src_file.name] = runner_digest
            installed_prompts.append(
                InstalledPrompt(
                    prompt_id=prompt_id,
                    files=files,
                    displaced_original_sha256=displaced_hashes,
                )
            )
            prompt_records.append(
                {
                    "prompt_id": prompt_id,
                    "installed_runner_sha256": dict(sorted(files.items())),
                    "displaced_subject_sha256": dict(sorted(displaced_hashes.items())),
                }
            )
        prompt_manifest_path = evidence_root / "prompt_collision_manifest.json"
        prompt_manifest_path.write_text(
            json.dumps({"prompts": prompt_records}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    manifest_path = evidence_root / "collision_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "subject_root": str(subject_root),
                "floor_hash": floor_hash(),
                "displaced": [
                    {
                        "path": d.path,
                        "original_sha256": d.original_sha256,
                        "installed_floor_sha256": d.installed_floor_sha256,
                    }
                    for d in displaced
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    report = verify_floor(intent_root)
    if (
        not report.clean
    ):  # pragma: no cover - defensive; reconciliation guarantees clean
        raise SubjectCopyError(
            f"floor not clean after reconciliation: {report.describe()}"
        )

    return ExecutionCopy(
        target_root=target_root,
        intent_root=intent_root,
        evidence_root=evidence_root,
        floor_hash=floor_hash(),
        overlay_hash=overlay_hash(overlay_dir),
        overlay_files=tuple(written),
        displaced=tuple(displaced),
        collision_manifest_path=manifest_path,
        prompts=tuple(installed_prompts),
        prompt_collision_manifest_path=prompt_manifest_path,
    )


# ID: 280c2998-cefb-4e53-a974-cc4a45a27580
def write_evidence_json(
    evidence_root: Path, name: str, payload: dict[str, Any]
) -> Path:
    """Write one JSON document into a run's evidence tree (and only there).

    *evidence_root* is the ``<run>/evidence/`` directory
    :func:`materialize_execution_copy` created; *name* is a bare filename.
    Deterministic encoding (sorted keys) so evidence is diffable.
    """
    evidence_root = Path(evidence_root)
    if "/" in name or name in ("", ".", ".."):
        raise ValueError(f"evidence file name must be a bare filename: {name!r}")
    if not evidence_root.is_dir() or evidence_root.name != "evidence":
        raise ValueError(f"not a run evidence directory: {evidence_root}")
    path = evidence_root / name
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    return path
