# src/cli/logic/byor.py

"""
BYOR onboarding — deliver the authored starter-intent into an external repository.

Per ADR-111, `core-admin project onboard <target>` DELIVERS the authored starter
constitution (`examples/starter-intent/.intent/`) into the target repo: the
machinery floor + the four-rule starter constitution, copied verbatim. It does
NOT generate a constitution from the target's code (ADR-111 D2; UR-04 — the human
owns the law) and is NOT a copy of CORE's full `.intent/` (ADR-108).

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

import os
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from body.atomic.executor import ActionExecutor
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext


logger = getLogger(__name__)

# ADR-111 D1/D4: examples/starter-intent/ is the canonical delivery payload
# (ADR-108 D2 source-of-truth), located relative to the running CORE repo root.
# Source-tree invocation reads it from there; wheel invocation is gated on
# ADR-108 D3 (machinery-in-wheel, issue #674).
_STARTER_REL = ("examples", "starter-intent", ".intent")


# ID: 8b2ee927-9c35-4125-b291-22669733e531
async def initialize_repository(
    context: CoreContext,
    path: Path,
    dry_run: bool = True,
) -> None:
    """
    Deliver the authored starter `.intent/` constitution into an external repo.

    Copies the machinery floor + the four-rule starter constitution from the
    canonical starter (ADR-111 D1) into ``<target>/.intent/``. Refuses if the
    target already has an ``.intent/`` (ADR-111 D3 — never overwrite an existing
    constitution). Dry-run by default; ``dry_run=False`` applies the writes via
    the ``file.create`` atomic action.
    """
    target_root = Path(path).resolve()
    write = not dry_run

    # CORE's repo root (the running install) anchors both the starter payload
    # and the file.create path base.
    core_root = context.git_service.repo_path.resolve()
    starter_dir = core_root.joinpath(*_STARTER_REL)

    # ADR-111 D4: the payload must be present. From source it is; from an
    # installed wheel it ships only after ADR-108 D3 (#674). Fail loud rather
    # than silently deliver nothing.
    if not starter_dir.is_dir():
        logger.error(
            "Starter constitution not found at %s. From an installed wheel this is "
            "gated on ADR-108 D3 (machinery-in-wheel, issue #674); run from the CORE "
            "source tree until it lands.",
            starter_dir,
        )
        raise typer.Exit(code=1)

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

    source_files = sorted(p for p in starter_dir.rglob("*") if p.is_file())
    executor = ActionExecutor(context)

    mode = "WRITE" if write else "DRY RUN"
    logger.info(
        "🚀 BYOR onboarding %s — delivering authored starter (%d files) [%s]",
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
            "💧 Dry run complete — %d files would be delivered to %s. "
            "Pass --write to apply.",
            len(source_files),
            target_intent,
        )
        return

    logger.info(
        "🎉 Delivered %d/%d starter files to %s.",
        delivered,
        len(source_files),
        target_intent,
    )
    logger.info(
        "Next: author your rules in .intent/rules/, then run "
        "`core-admin code audit --offline` (or wire the F-10 CI Action) against this repo."
    )
    if delivered < len(source_files):
        raise typer.Exit(code=1)
