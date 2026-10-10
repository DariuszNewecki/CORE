# src/cli/logic/byor.py

"""
BYOR onboarding — deliver the machinery floor into an external repository.

Per ADR-111 (amended by ADR-119 D2/D6), `core project onboard <target>`
delivers ONLY the machinery floor — META schemas, taxonomies, constitution stub,
and enforcement/config — into the target repo's `.intent/`. No rules, no mappings.
Rules are per-repo-inducted by `project scout` (Phase B) or authored manually.

CONSTITUTIONAL NOTES (#640):
- Writes route through the `file.create` atomic action via `ActionExecutor`
  (ADR-111 D3), the same sanctioned scaffold surface `project new` uses. A direct
  `FileHandler.write` on a literal `.intent/` path is hard-blocked by the
  governed-artifact tier; delivery targets the external repo through a
  CORE-root-relative path that does not match the `.intent/` prefix, so it
  classifies as writable.
- Removed the dead `TEMPLATES_DIR` path and the `KnowledgeGraphBuilder`
  generate-law-from-code path (ADR-111 D1/D2).
"""

from __future__ import annotations

import importlib.resources
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from body.services.outside_write_ledger import OutsideWriteLog
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext


logger = getLogger(__name__)

# ADR-119 D2: machinery floor = META + constitution + enforcement/config + taxonomies.
# Rules and enforcement/mappings are Phase B (project scout), never delivered here.
_MACHINERY_FLOOR_PREFIXES = (
    "META/",
    "constitution/",
    "enforcement/config/",
    "taxonomies/",
)

# Stage directory root (ADR-123 D1). Relative to CORE's repo root; gitignored by work/*.
_STAGE_ROOT = Path("work") / "staged"


# ID: c5859705-b466-4050-bd08-e6aebc2e2e89
def _stage_dir_for(core_root: Path, target_path: Path) -> Path:
    """Canonical stage directory for a given target repository (ADR-123 D1).

    ``work/staged/<basename>/`` within CORE's repo, where ``<basename>`` is
    the target path's directory name. Gitignored by ``work/*``.
    """
    return core_root / _STAGE_ROOT / Path(target_path).resolve().name


# Universally-dangerous write targets — refused regardless of overlap with
# CORE's own tree. Not an attempt to enumerate every sensitive path; a fixed
# backstop for the obviously-wrong ones (CodeQL py/path-injection, #787).
_UNSAFE_TARGET_ROOTS = frozenset(
    Path(p)
    for p in (
        "/",
        "/etc",
        "/bin",
        "/sbin",
        "/usr",
        "/boot",
        "/sys",
        "/proc",
        "/dev",
        "/root",
        "/lib",
        "/lib64",
    )
)


# ID: 1463e14d-c6e9-4c36-8e30-f8342022bb63
def core_source_root() -> Path | None:
    """CORE's own repository root when running from a source checkout, else None.

    The overlap guard protects CORE's own repository from BYOR writes. That
    repository is the source tree the running code was loaded from — not the
    repository found by walking up from the current directory, which for a
    ``pip install core-runtime`` user is *their* repository. An installed
    wheel has no CORE repository to protect, so this returns None there.
    """
    from shared.config import REPO_ROOT

    root = REPO_ROOT.resolve()
    return root if (root / ".intent").is_dir() else None


# ID: cdf75615-3371-4b61-9e19-4ad12fbe0de7
def _reject_unsafe_target(target_root: Path, core_root: Path | None) -> None:
    """Refuse a BYOR target that would corrupt the running install or a system dir.

    BYOR intentionally writes ``.intent/`` into an operator-specified external
    path — that write-anywhere-on-host-the-operator-names capability is the
    feature, bounded primarily by ADR-054 D3's loopback-only, single-operator
    trust boundary (no path sanitization can substitute for that; a caller who
    can reach the API can already reach the filesystem directly). This is a
    defense-in-depth backstop only: refuse the two shapes of self-inflicted
    damage that have no legitimate BYOR use — targeting CORE's own repo tree,
    or a fixed set of universally-dangerous system directories.

    ``core_root`` is None when there is no CORE repository to protect (an
    installed wheel, see :func:`core_source_root`); only the system-directory
    backstop applies then.
    """
    overlaps_core = core_root is not None and (
        target_root == core_root
        or core_root in target_root.parents
        or target_root in core_root.parents
    )
    if overlaps_core:
        logger.error(
            "Refusing external target %s — overlaps CORE's own repo root %s",
            target_root,
            core_root,
        )
        raise typer.Exit(code=1)
    if target_root in _UNSAFE_TARGET_ROOTS:
        logger.error(
            "Refusing external target %s — system-critical directory", target_root
        )
        raise typer.Exit(code=1)


# ID: e21c1b19-792b-46fb-b558-2102cc49e3b2
def deliver_external_intent_files(
    target_root: Path,
    core_root: Path | None,
    files: dict[str, str],
    outside: OutsideWriteLog | None = None,
) -> int:
    """Write text files into an external target's ``.intent/`` (ADR-111 D3 lane).

    The single sanctioned write surface for BYOR delivery into a repository
    that is not CORE's own: ``initialize_repository`` and ``promote_staged``
    copy the machinery floor through the same stdlib path, and ``project
    adopt-pack`` (ADR-149) delivers pack rule/mapping documents through this
    helper. ``FileHandler`` cannot serve these writes — it is repo-bound and
    hard-blocks any literal ``.intent/`` prefix at the governed-artifact tier
    — which is why this module is excluded by name from
    ``governance.mutation_surface.filehandler_required``.

    ``files`` maps target-relative paths (each MUST start with ``.intent/``)
    to text content. Refuses the same targets ``_reject_unsafe_target``
    refuses, so a pack can never be written into CORE's own constitution.
    Returns the number of files written. No git-add: the operator commits.
    Each written file is added to ``outside`` (ADR-169 D5); the caller flushes
    it — this helper is synchronous and the ledger is not.
    """
    target_root = target_root.resolve()
    _reject_unsafe_target(
        target_root, core_root.resolve() if core_root is not None else None
    )
    for rel in files:
        if not rel.startswith(".intent/") or ".." in Path(rel).parts:
            raise ValueError(
                f"deliver_external_intent_files: {rel!r} is not a .intent/-relative path"
            )
    written = 0
    for rel, content in files.items():
        dest = target_root / rel
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
        except OSError as exc:
            logger.error(
                "Target path not accessible on the CORE host: %s (%s)", dest, exc
            )
            raise typer.Exit(code=1) from exc
        if outside is not None:
            outside.wrote(dest)
        written += 1
    return written


# ID: 3f7a1c82-e4d9-4b6e-9c21-d58f02a7b3e1
def _resolve_machinery_floor(core_root: Path | None) -> Path:
    """
    Locate the machinery floor directory (ADR-108 D3).

    Always resolves from the bundled ``shared._machinery_floor`` package data —
    present for both editable (source-tree) installs and installed wheels.
    The ``examples/starter-intent/`` source-tree path was the pre-D3 fallback;
    after D3 the starter contains only the rules layer, not the floor.
    """
    bundled = Path(
        str(importlib.resources.files("shared").joinpath("_machinery_floor"))
    )
    if bundled.is_dir():
        return bundled
    raise RuntimeError(
        "Machinery floor not found in wheel package data. "
        "This is a packaging error — please report it."
    )


def _machinery_floor_files(starter_dir: Path) -> list[Path]:
    """The machinery-floor files delivered into a target's ``.intent/``.

    Single selection shared by ``initialize_repository`` (project onboard) and
    ``cli.logic.project_scaffold`` (project new, ADR-119 Amendment 2026-10-02), so
    both deliver the same floor. ADR-119 D2: floor only — ``rules/`` and
    ``enforcement/mappings/`` are excluded by the prefix set.
    """
    return sorted(
        p
        for p in starter_dir.rglob("*")
        if p.is_file()
        and not any(part.startswith("__") for part in p.parts)
        and any(
            p.relative_to(starter_dir).as_posix().startswith(prefix)
            for prefix in _MACHINERY_FLOOR_PREFIXES
        )
    )


# ID: 8b2ee927-9c35-4125-b291-22669733e531
async def initialize_repository(
    context: CoreContext,
    path: Path,
    dry_run: bool = True,
    stage_dir: Path | None = None,
) -> None:
    """Deliver the machinery floor into an external repo (BYOR Phase A).

    Copies META schemas, taxonomies, constitution stub, and enforcement/config
    from the bundled machinery floor (``shared._machinery_floor``, ADR-119 D9)
    into ``<target>/.intent/``. Rules
    and mappings are excluded — those are Phase B (``project scout``). Refuses if
    the target already has an ``.intent/`` (ADR-111 D3). Dry-run by default;
    ``dry_run=False`` applies the writes via the ``file.create`` atomic action.

    When ``stage_dir`` is provided (and write mode is active), files land in the
    stage directory instead of the real target. The ``.intent/`` existence check is
    skipped — re-staging overwrites (ADR-123 D1).
    """
    target_root = Path(path).resolve()
    write = not dry_run

    # CORE's repo root (the running install) anchors the file.create path base.
    core_root = context.git_service.repo_path.resolve()
    _reject_unsafe_target(target_root, core_root)
    try:
        starter_dir = _resolve_machinery_floor(core_root)
    except RuntimeError as exc:
        logger.error("%s", exc)
        raise typer.Exit(code=1) from exc

    # Stage mode: write to stage_dir; skip .intent/ existence check (idempotent re-stage).
    # Direct mode: ADR-111 D3 never overwrite an existing constitution.
    if stage_dir is not None and write:
        dest_root = stage_dir
    else:
        dest_root = target_root
        target_intent = target_root / ".intent"
        try:
            target_intent_exists = target_intent.exists()
        except OSError as exc:
            logger.error(
                "Target path not accessible on the CORE host: %s (%s)",
                target_intent,
                exc,
            )
            raise typer.Exit(code=1) from exc
        if target_intent_exists:
            logger.error(
                "Target already has a constitution at %s. CORE will not overwrite an "
                "existing .intent/. Remove it first if you intend to re-scaffold.",
                target_intent,
            )
            raise typer.Exit(code=1)

    # ADR-119 D2: machinery floor only — exclude rules/ and enforcement/mappings/.
    source_files = _machinery_floor_files(starter_dir)

    dest_label = f"stage:{dest_root}" if stage_dir is not None else str(target_root)
    mode = "WRITE" if write else "DRY RUN"
    logger.info(
        "🚀 BYOR onboarding %s — delivering machinery floor (%d files) [%s]",
        dest_label,
        len(source_files),
        mode,
    )

    # Direct stdlib writes to the external target (ADR-111 D3 sanctioned exception:
    # FileHandler's is_relative_to boundary guard cannot cross the repo boundary to an
    # external project; byor.py is excluded from no_direct_writes in mutation_surface.yaml
    # for this reason). No git-add: the operator commits .intent/ in the target repo.
    # ADR-169 D5: writes into the external target are recorded; a stage lives
    # inside CORE's own repository and is not an outside write.
    outside = (
        OutsideWriteLog(target_root, produced_by="project.onboard")
        if write and stage_dir is None
        else None
    )
    if outside is not None:
        await outside.require_ledger()  # no ledger, no write (#953)
    delivered = 0
    try:
        for src in source_files:
            rel = src.relative_to(starter_dir)
            dest = dest_root / ".intent" / rel
            if write:
                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
                except OSError as exc:
                    logger.error(
                        "Target path not accessible on the CORE host: %s (%s)",
                        dest,
                        exc,
                    )
                    raise typer.Exit(code=1) from exc
                if not dest.is_file():
                    logger.error("   ❌ not delivered: %s", rel)
                    continue
                if outside is not None:
                    outside.wrote(dest)
            delivered += 1
            logger.info("   -> %s %s", "✅" if write else "[DRY RUN] would write", rel)
    finally:
        if outside is not None:
            await outside.flush()

    if not write:
        logger.info(
            "💧 Dry run complete — %d machinery-floor files would be delivered to %s. "
            "Pass --write to apply.",
            len(source_files),
            target_root / ".intent",
        )
        return

    if stage_dir is not None:
        logger.info(
            "📦 Staged %d/%d machinery-floor files to %s.",
            delivered,
            len(source_files),
            dest_root / ".intent",
        )
        return

    logger.info(
        "🎉 Delivered %d/%d machinery-floor files to %s.",
        delivered,
        len(source_files),
        target_root / ".intent",
    )
    logger.info(
        "Next: run `core-admin project scout <target> [--write]` to induce and ratify "
        "rules for this repo, then `core-admin code audit --offline --target <target>` "
        "to enforce them."
    )
    if delivered < len(source_files):
        raise typer.Exit(code=1)


# ID: 20e68432-240d-4cb4-854c-ccf815ac5176
async def promote_staged(context: CoreContext, path: Path) -> None:
    """Promote a staged machinery floor into the target repository (ADR-123 D2).

    Reads from ``work/staged/<basename>/.intent/`` (within CORE's repo) and writes
    to ``<path>/.intent/`` via the ``file.create`` atomic action — the same governed
    surface as the direct write. Cleans up the stage directory on success.

    Refuses if:
    - The stage directory does not exist (operator must stage first).
    - The target already has ``.intent/`` (ADR-111 D3 / ADR-123 D2 safety invariant).
    """
    target_root = Path(path).resolve()
    core_root = context.git_service.repo_path.resolve()
    _reject_unsafe_target(target_root, core_root)
    stage_dir = _stage_dir_for(core_root, target_root)
    stage_intent = stage_dir / ".intent"

    if not stage_dir.is_dir():
        logger.error(
            "No staged content found at %s — "
            "run `core project onboard %s --write --stage` first.",
            stage_dir,
            path,
        )
        raise typer.Exit(code=1)

    if not stage_intent.is_dir():
        logger.error(
            "Stage at %s exists but has no .intent/ subdirectory. "
            "Re-run `core project onboard %s --write --stage` to refresh.",
            stage_dir,
            path,
        )
        raise typer.Exit(code=1)

    # ADR-111 D3 / ADR-123 D2: same overwrite guard as the direct write path.
    target_intent = target_root / ".intent"
    try:
        target_intent_exists = target_intent.exists()
    except OSError as exc:
        logger.error(
            "Target path not accessible on the CORE host: %s (%s)", target_intent, exc
        )
        raise typer.Exit(code=1) from exc
    if target_intent_exists:
        logger.error(
            "Target already has a constitution at %s. "
            "CORE will not overwrite an existing .intent/. "
            "Remove it first if you intend to re-scaffold.",
            target_intent,
        )
        raise typer.Exit(code=1)

    source_files = sorted(p for p in stage_intent.rglob("*") if p.is_file())
    if not source_files:
        logger.error("Stage at %s is empty. Re-stage before promoting.", stage_dir)
        raise typer.Exit(code=1)

    # Direct stdlib writes to external target (same sanctioned exception as
    # initialize_repository — FileHandler boundary guard cannot cross repos).
    # ADR-169 D5: every file promoted into the target is recorded.
    outside = OutsideWriteLog(target_root, produced_by="project.onboard.promote")
    await outside.require_ledger()  # no ledger, no write (#953)
    delivered = 0
    try:
        for src in source_files:
            rel = src.relative_to(stage_intent)
            dest = target_intent / rel
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
            except OSError as exc:
                logger.error(
                    "Target path not accessible on the CORE host: %s (%s)", dest, exc
                )
                raise typer.Exit(code=1) from exc
            if not dest.is_file():
                logger.error("   ❌ not delivered: %s", rel)
                continue
            outside.wrote(dest)
            delivered += 1
            logger.info("   -> ✅ %s", rel)
    finally:
        await outside.flush()

    # ADR-123 D2 step 5: remove stage on success.
    shutil.rmtree(stage_dir)

    logger.info(
        "🎉 Promoted %d/%d files to %s. Stage cleaned up.",
        delivered,
        len(source_files),
        target_intent,
    )
    logger.info(
        "Next: run `core-admin project scout <target> [--write]` to induce and ratify "
        "rules for this repo, then `core-admin code audit --offline --target <target>` "
        "to enforce them."
    )
    if delivered < len(source_files):
        raise typer.Exit(code=1)
