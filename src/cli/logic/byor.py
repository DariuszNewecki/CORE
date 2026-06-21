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
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from body.atomic.executor import ActionExecutor
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext


logger = getLogger(__name__)

# ADR-111 D1/D4: examples/starter-intent/ is the canonical source for the
# machinery floor (ADR-108 D2; ADR-119 D8). Located relative to the running
# CORE repo root. ADR-108 D3 / #674: wheel fallback via shared._machinery_floor.
_STARTER_REL = ("examples", "starter-intent", ".intent")

# ADR-119 D2: machinery floor = META + constitution + enforcement/config + taxonomies.
# Rules and enforcement/mappings are Phase B (project scout), never delivered here.
_MACHINERY_FLOOR_PREFIXES = (
    "META/",
    "constitution/",
    "enforcement/config/",
    "taxonomies/",
)


# ID: 3f7a1c82-e4d9-4b6e-9c21-d58f02a7b3e1
def _resolve_machinery_floor(core_root: Path) -> Path:
    """
    Locate the machinery floor directory (ADR-108 D3).

    Resolution order:
    1. Source tree — ``examples/starter-intent/.intent/`` relative to *core_root*.
       Present on dev and editable installs; takes priority.
    2. Wheel package data — ``shared/_machinery_floor/`` bundled in the
       ``core-runtime`` wheel (ADR-108 D3 / ADR-119 D9, issue #674).
    """
    source = core_root.joinpath(*_STARTER_REL)
    if source.is_dir():
        return source
    bundled = Path(
        str(importlib.resources.files("shared").joinpath("_machinery_floor"))
    )
    if bundled.is_dir():
        logger.info("Using bundled machinery floor from wheel package data.")
        return bundled
    raise RuntimeError(
        f"Machinery floor not found at {source} or in wheel package data. "
        "This is a packaging error — please report it."
    )


# ID: 8b2ee927-9c35-4125-b291-22669733e531
async def initialize_repository(
    context: CoreContext,
    path: Path,
    dry_run: bool = True,
) -> None:
    """
    Deliver the machinery floor into an external repo (BYOR Phase A).

    Copies META schemas, taxonomies, constitution stub, and enforcement/config
    from ``examples/starter-intent/.intent/`` into ``<target>/.intent/``. Rules
    and mappings are excluded — those are Phase B (``project scout``). Refuses if
    the target already has an ``.intent/`` (ADR-111 D3). Dry-run by default;
    ``dry_run=False`` applies the writes via the ``file.create`` atomic action.
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

    # ADR-111 D3: never overwrite an existing constitution.
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
    rel_base = os.path.relpath(target_root, core_root)

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

    mode = "WRITE" if write else "DRY RUN"
    logger.info(
        "🚀 BYOR onboarding %s — delivering machinery floor (%d files) [%s]",
        target_root,
        len(source_files),
        mode,
    )

    # Ensure the target's .intent/ subdirectories exist before file.create.
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
            target_intent,
        )
        return

    logger.info(
        "🎉 Delivered %d/%d machinery-floor files to %s.",
        delivered,
        len(source_files),
        target_intent,
    )
    logger.info(
        "Next: run `core-admin project scout <target> [--write]` to induce and ratify "
        "rules for this repo, then `core-admin code audit --offline` to enforce them."
    )
    if delivered < len(source_files):
        raise typer.Exit(code=1)
