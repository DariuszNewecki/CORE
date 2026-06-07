# src/shared/infrastructure/context/shadow_materializer.py

"""
materialize_workspace_for_audit — build a shadow tempdir for audit-over-shadow.

The constitutional audit engine walks `repo_path.rglob("*")` and reads files
via `file_path.read_text()`. To run that engine over a LimbWorkspace's
proposed (uncommitted) changes without modifying the engine, we materialize
a tempdir that LOOKS like the repo:

  - every src/ file is a symlink to the real file, OR a real file containing
    the crate's proposed content when the path is in the workspace's crate
  - .intent/, tests/, pyproject.toml, and other audit-relevant top-level
    entries are symlinked wholesale (read-only, no overlay)
  - var/ is rebuilt as a real dir containing symlinks to its children EXCEPT
    var/tmp/ (which would otherwise pull the shadow tempdir itself back into
    the walk, creating a cycle)
  - structural excludes (.git, .venv, node_modules, __pycache__, dist, build)
    are skipped entirely — they match the auditor's own structural-exclude set

The result: pointing AuditorContext at the tempdir produces an audit whose
file-read content is byte-equivalent to running the audit against a repo
where the crate had been committed. No engine changes; no caller-side wiring
beyond materialization; symlinks die with the tempdir on context exit.

Constitutional alignment:
- Pillar I (Octopus): the "Isolate" stage of the V2.3 Limb Operational Model.
- Pillar II (UNIX): single responsibility — materialize a shadow tree.
- CLAUDE.md /tmp/ prohibition: tempdir lives under var/tmp/, never /tmp/.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.infrastructure.context.limb_workspace import LimbWorkspace


logger = getLogger(__name__)


# Mirrors mind.governance.audit_context._STRUCTURAL_DIR_PARTS. Kept local
# to avoid Body→Mind import; if the canonical set ever changes, the audit
# itself prunes through ITS copy at walk-time and our shadow harmlessly
# carries the extra symlinks. The shadow is only an input surface.
_STRUCTURAL_EXCLUDES: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        "dist",
        "build",
    }
)


# ID: bb4e8509-b838-483f-af29-516d42e5aa59
@contextmanager
def materialize_workspace_for_audit(
    workspace: LimbWorkspace,
    repo_root: Path,
) -> Iterator[Path]:
    """Context manager yielding a Path to a shadow tempdir audit can walk.

    Args:
        workspace: A LimbWorkspace whose crate carries the proposed changes.
        repo_root: The real repo root the audit would otherwise walk.

    Yields:
        Path to the shadow tempdir. Pass this as `repo_path` to
        `run_stateless_audit(intent_repo, repo_path)` — the audit will walk
        the shadow, read crate-overlaid content for in-crate paths, and read
        canonical disk content (via symlinks) for everything else.

    The tempdir and all its symlinks/files are removed on context exit.
    """
    repo_root = Path(repo_root).resolve()
    tmp_parent = repo_root / "var" / "tmp"
    tmp_parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix="core-shadow-", dir=str(tmp_parent)
    ) as raw_tmp:
        shadow_root = Path(raw_tmp)
        crate = workspace.get_crate_content()

        _materialize_top_level(repo_root, shadow_root)
        _materialize_src_tree(repo_root, shadow_root, crate)
        _overlay_non_src_crate_files(shadow_root, crate)

        logger.info(
            "Shadow materialized at %s (crate=%d files)", shadow_root, len(crate)
        )
        yield shadow_root


def _materialize_top_level(repo_root: Path, shadow_root: Path) -> None:
    """Symlink every top-level repo entry into the shadow, except src/ and excludes.

    src/ is handled separately by _materialize_src_tree (per-file symlinks
    so individual crate-file overlays don't bleed through a directory
    symlink onto the real repo). var/ is rebuilt as a real dir with its
    children symlinked, skipping var/tmp/ to break the recursion that would
    otherwise pull the shadow tempdir back into the walk.
    """
    for entry in repo_root.iterdir():
        if entry.name in _STRUCTURAL_EXCLUDES:
            continue
        if entry.name == "src":
            continue
        if entry.name == "var":
            _materialize_var_dir(entry, shadow_root / "var")
            continue
        (shadow_root / entry.name).symlink_to(entry)


def _materialize_var_dir(real_var: Path, shadow_var: Path) -> None:
    """Build var/ as a real dir, symlink children, skip var/tmp/.

    The shadow tempdir itself lives under var/tmp/, so symlinking var/tmp/
    into the shadow would re-enter the shadow when the audit walker rglobs
    var/. Skipping it severs the cycle.
    """
    shadow_var.mkdir()
    for child in real_var.iterdir():
        if child.name == "tmp":
            continue
        (shadow_var / child.name).symlink_to(child)


def _materialize_src_tree(
    repo_root: Path,
    shadow_root: Path,
    crate: dict[str, str],
) -> None:
    """Per-file symlink the src/ tree, with crate-path files left empty for overlay.

    The walk uses rglob("*") so it sees every file the auditor's own walker
    would see. For each non-crate file, place a symlink to the real file.
    For each crate-path file, skip — _overlay_non_src_crate_files writes the
    real file in a second pass so we never accidentally symlink-then-overwrite.
    """
    real_src = repo_root / "src"
    if not real_src.exists():
        return
    shadow_src = shadow_root / "src"
    shadow_src.mkdir()

    crate_paths = set(crate.keys())

    for real_file in real_src.rglob("*"):
        if not real_file.is_file():
            continue
        # Skip structural-excluded subtrees (vendored __pycache__, etc.).
        rel = real_file.relative_to(repo_root)
        if any(part in _STRUCTURAL_EXCLUDES for part in rel.parts):
            continue
        rel_posix = rel.as_posix()
        # Crate overlays are written in the second pass.
        if rel_posix in crate_paths:
            continue
        shadow_file = shadow_root / rel
        shadow_file.parent.mkdir(parents=True, exist_ok=True)
        shadow_file.symlink_to(real_file)


def _overlay_non_src_crate_files(shadow_root: Path, crate: dict[str, str]) -> None:
    """Write every crate file as a real file in the shadow.

    Handles two cases together:
    - crate files under src/ (parents are real dirs from _materialize_src_tree)
    - top-level file crate paths (pyproject.toml etc.) where the symlink
      placed by _materialize_top_level must be replaced atomically

    Refuses to write any path whose ancestor chain inside the shadow contains
    a directory symlink — that would write THROUGH into the real repo.
    Crate paths under per-file-materialized subtrees (src/) are always safe;
    crate paths under directory-symlinked subtrees (.intent/, tests/, var/
    children, etc.) are refused. Extend _materialize_src_tree-style
    per-file materialization to additional subtrees before crating into them.
    """
    for rel_path, content in crate.items():
        dst = shadow_root / rel_path
        _guard_no_symlink_ancestor(shadow_root, dst, rel_path)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.is_symlink() or dst.exists():
            dst.unlink()
        dst.write_text(content, encoding="utf-8")


def _guard_no_symlink_ancestor(shadow_root: Path, dst: Path, rel_path: str) -> None:
    """Raise if any ancestor of dst (strictly inside shadow_root) is a symlink.

    Writing through a directory symlink would mutate the real repo (data
    loss / corruption). The guard makes the failure mode loud and named.
    """
    parent = dst.parent
    while parent != shadow_root and parent != parent.parent:
        if parent.is_symlink():
            raise ValueError(
                f"Crate path {rel_path!r} cannot be materialized: ancestor "
                f"{parent.relative_to(shadow_root).as_posix()!r} is a directory "
                "symlink and writing through it would mutate the real repo. "
                "Only src/ supports crate overlays in v1; extend "
                "_materialize_src_tree to handle other prefixes if needed."
            )
        parent = parent.parent


__all__ = ["materialize_workspace_for_audit"]
