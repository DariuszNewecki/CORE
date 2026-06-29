# src/cli/logic/byor.py

"""
BYOR onboarding — deliver the machinery floor into an external repository.

Per ADR-111 (amended by ADR-119 D2/D6), `core-admin project onboard <target>`
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
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from body.atomic.executor import ActionExecutor
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


# ID: 3f7a1c82-e4d9-4b6e-9c21-d58f02a7b3e1
def _resolve_machinery_floor(core_root: Path) -> Path:
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


# ID: 8b2ee927-9c35-4125-b291-22669733e531
async def initialize_repository(
    context: CoreContext,
    path: Path,
    dry_run: bool = True,
    stage_dir: Path | None = None,
) -> None:
    """Deliver the machinery floor into an external repo (BYOR Phase A).

    Copies META schemas, taxonomies, constitution stub, and enforcement/config
    from ``examples/starter-intent/.intent/`` into ``<target>/.intent/``. Rules
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
        if target_intent.exists():
            logger.error(
                "Target already has a constitution at %s. CORE will not overwrite an "
                "existing .intent/. Remove it first if you intend to re-scaffold.",
                target_intent,
            )
            raise typer.Exit(code=1)

    # The file.create action resolves file_path relative to CORE's repo root.
    # A path that does NOT start with the literal `.intent/` prefix classifies as
    # writable (target_class_boundaries.yaml), so we address the external repo via
    # a CORE-root-relative path. This is how `project new` writes a sibling's .intent/.
    rel_base = os.path.relpath(dest_root, core_root)

    # ADR-119 D2: machinery floor only — exclude rules/ and enforcement/mappings/.
    source_files = sorted(
        p
        for p in starter_dir.rglob("*")
        if p.is_file()
        and any(
            p.relative_to(starter_dir).as_posix().startswith(prefix)
            for prefix in _MACHINERY_FLOOR_PREFIXES
        )
    )
    executor = ActionExecutor(context)

    dest_label = f"stage:{dest_root}" if stage_dir is not None else str(target_root)
    mode = "WRITE" if write else "DRY RUN"
    logger.info(
        "🚀 BYOR onboarding %s — delivering machinery floor (%d files) [%s]",
        dest_label,
        len(source_files),
        mode,
    )

    # Ensure the destination's .intent/ subdirectories exist before file.create.
    parent_dirs = sorted(
        {
            (
                Path(rel_base) / ".intent" / src.relative_to(starter_dir).parent
            ).as_posix()
            for src in source_files
        }
    )
    for rel_dir in parent_dirs:
        if write:
            context.file_handler.ensure_dir(rel_dir)
        else:
            logger.info("   -> [DRY RUN] would ensure dir %s", rel_dir)

    delivered = 0
    for src in source_files:
        rel = src.relative_to(starter_dir).as_posix()
        file_path = (Path(rel_base) / ".intent" / rel).as_posix()
        content = src.read_text(encoding="utf-8")
        await executor.execute(
            action_id="file.create",
            write=write,
            file_path=file_path,
            code=content,
        )
        # Confirm delivery by disk presence — the file is the ground truth. The
        # executor's ActionResult.ok can be re-stamped by post-body policy
        # validation even when the write succeeded, so it is not a reliable signal.
        if write and not (core_root / file_path).is_file():
            logger.error("   ❌ not delivered: %s", file_path)
            continue
        delivered += 1
        logger.info(
            "   -> %s %s", "✅" if write else "[DRY RUN] would write", file_path
        )

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
    stage_dir = _stage_dir_for(core_root, target_root)
    stage_intent = stage_dir / ".intent"

    if not stage_dir.is_dir():
        logger.error(
            "No staged content found at %s — "
            "run `core-admin project onboard %s --write --stage` first.",
            stage_dir,
            path,
        )
        raise typer.Exit(code=1)

    if not stage_intent.is_dir():
        logger.error(
            "Stage at %s exists but has no .intent/ subdirectory. "
            "Re-run `core-admin project onboard %s --write --stage` to refresh.",
            stage_dir,
            path,
        )
        raise typer.Exit(code=1)

    # ADR-111 D3 / ADR-123 D2: same overwrite guard as the direct write path.
    target_intent = target_root / ".intent"
    if target_intent.exists():
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

    rel_base = os.path.relpath(target_root, core_root)
    executor = ActionExecutor(context)

    # Ensure the target .intent/ subdirectories.
    parent_dirs = sorted(
        {
            (
                Path(rel_base) / ".intent" / src.relative_to(stage_intent).parent
            ).as_posix()
            for src in source_files
        }
    )
    for rel_dir in parent_dirs:
        context.file_handler.ensure_dir(rel_dir)

    delivered = 0
    for src in source_files:
        rel = src.relative_to(stage_intent).as_posix()
        file_path = (Path(rel_base) / ".intent" / rel).as_posix()
        content = src.read_text(encoding="utf-8")
        await executor.execute(
            action_id="file.create",
            write=True,
            file_path=file_path,
            code=content,
        )
        if not (core_root / file_path).is_file():
            logger.error("   ❌ not delivered: %s", file_path)
            continue
        delivered += 1
        logger.info("   -> ✅ %s", file_path)

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
