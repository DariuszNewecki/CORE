# src/body/atomic/sandbox_lifecycle.py
"""
SandboxLifecycle — ADR-071 D2.2 sandbox decision + copy-back subsystem.

Extracted from ActionExecutor (2026-06-01). The "decide whether to sandbox
this execution" logic and the "copy worktree mutations back to main tree"
logic are one cohesive subsystem — both gated on the same ADR-071 D2.2
conditions, both operating on the same `ScopedGitService` instance, both
sharing the same conflict/no-deletion safety contract.

Co-locating them here keeps ActionExecutor focused on its single
constitutional responsibility — orchestrating the policy/auth/exec/hooks/
audit pipeline — and gives the sandbox subsystem a name that matches what
it is. No behavioral change vs. the in-class implementation; ActionExecutor
constructs one SandboxLifecycle and delegates two call sites to it.

LAYER: body/atomic — execution-infrastructure helper. No LLM, no rule
evaluation. Reads from CoreContext (git_service, file_handler); writes
only through FileHandler.write_validated_bytes (ADR-021 commit_paths
boundary preserved).
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

from body.atomic.registry import ActionDefinition
from shared.action_types import ActionImpact
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)

# ADR-071 D2.2 Phase 2: action impacts that warrant hermetic worktree
# sandboxing. WRITE_DATA targets databases/external systems (not the
# source tree), so the worktree isolation does nothing for it.
_SANDBOXED_IMPACTS = frozenset({ActionImpact.WRITE_CODE, ActionImpact.WRITE_METADATA})


# ID: 8c112a60-ad77-431b-9825-dcdcc63afb55
class SandboxLifecycle:
    """
    ADR-071 D2.2 sandbox decision + copy-back subsystem.

    Two public methods, both operating on the same scoped-git instance:

    - `build_execution_context` — decide whether to sandbox the about-to-run
      action, and if so produce a scoped CoreContext with `git_service` and
      `file_handler` repointed at a fresh ScopedGitService worktree.

    - `propagate_changes` — after a successful sandboxed run, copy the
      worktree's modified/untracked files back to the main tree through
      `FileHandler.write_validated_bytes`, with a conflict check that
      refuses to overwrite uncommitted main-tree changes (loud-failure
      contract).

    Both methods are pure delegations of subsystem state — they share no
    in-flight state between calls. ActionExecutor holds the instance and
    drives both call sites within a single `execute()` invocation, passing
    the `scoped_git` handle between them.
    """

    def __init__(self, core_context: CoreContext):
        """
        Initialize the sandbox subsystem against the main CoreContext.

        Args:
            core_context: The main (unsandboxed) CoreContext. Used to
                read `git_service` (worktree creation), `file_handler`
                (copy-back target), and as the base for the scoped
                context built per execution.
        """
        self.core_context = core_context

    # ID: a9b3e7c1-4d2f-4e85-9a17-6b8c3d5e7f12
    def build_execution_context(
        self,
        definition: ActionDefinition,
        write: bool,
        pre_execution_sha: str | None,
    ) -> tuple[CoreContext, Any]:
        """Decide whether to sandbox this execution and build the context.

        Returns (context_to_pass_to_action, scoped_git_or_None). When
        sandboxing applies, the returned context is a shallow copy of
        self.core_context with `git_service` and `file_handler` repointed
        at a fresh ScopedGitService rooted at `pre_execution_sha`. The
        caller MUST call `scoped_git.cleanup()` in a finally block.

        Gate (all required):
          - pre_execution_sha is not None (autonomous call path)
          - write is True (dry-runs need no isolation)
          - the action's @atomic_action metadata declares impact ∈
            {WRITE_CODE, WRITE_METADATA}

        Note on IntentGuard: the FileHandler constructor wires an
        IntentGuard via get_intent_guard(), which is a process singleton
        bound to the first repo_path it sees. A scoped FileHandler reuses
        that singleton — paths are still validated against governance,
        but using main-repo .intent/ state (the current governance frame)
        rather than the worktree's snapshot. That's the correct default:
        we want to honour governance as-of-now, not as-of-proposal.
        """
        if (
            pre_execution_sha is None
            or not write
            or self.core_context.git_service is None
        ):
            return self.core_context, None

        metadata = getattr(definition.executor, "_atomic_action_metadata", None)
        if metadata is None or metadata.impact not in _SANDBOXED_IMPACTS:
            return self.core_context, None

        from shared.infrastructure.storage.file_handler import FileHandler

        scoped_git = self.core_context.git_service.create_worktree(pre_execution_sha)
        try:
            scoped_file_handler = FileHandler(str(scoped_git.repo_path))
        except Exception:
            scoped_git.cleanup()
            raise

        scoped_context = dataclasses.replace(
            self.core_context,
            git_service=scoped_git,
            file_handler=scoped_file_handler,
        )
        logger.info(
            "SandboxLifecycle: %s sandboxed in %s at sha %s",
            definition.action_id,
            scoped_git.repo_path,
            pre_execution_sha[:12],
        )
        return scoped_context, scoped_git

    # ID: b1d2c5f9-3a48-4e67-8b91-2c5f8a3d6e90
    def propagate_changes(self, scoped_git: Any) -> None:
        """Copy files modified inside the sandbox back to the main tree.

        Walks `scoped_git.status_porcelain()` and for each modified or
        untracked entry, copies the worktree-side bytes through the main
        FileHandler's write_runtime_bytes surface (canonical write path,
        no re-syntax-check, no auto-newline injection — byte-identical).

        Before copying anything, checks the main tree for uncommitted
        modifications in the sandbox's target paths. If any overlap, raises
        — the exception bubbles into execute()'s outer try and turns the
        action result into a loud failure, rather than silently overwriting
        the governor's concurrent edits. This is the safety mechanism the
        ADR-071 D2.2 plan describes as "loud failure rather than silent
        contamination". The b11f4dba race shape is closed: worker either
        propagates cleanly (no overlap) or refuses (overlap detected).

        Deletions are not propagated: the no_direct_writes rule (#451)
        forbids @atomic_action functions from invoking unlink/rmdir, so
        a `D`-status entry here would itself be a constitutional
        violation. We log and skip rather than silently deleting from
        the main tree.
        """
        sandbox_root = scoped_git.repo_path
        file_handler = self.core_context.file_handler

        try:
            porcelain = scoped_git.status_porcelain()
        except Exception as exc:
            logger.error(
                "SandboxLifecycle: sandbox status read failed (%s); "
                "main tree NOT updated to avoid partial propagation",
                exc,
            )
            return

        if not porcelain:
            logger.debug(
                "SandboxLifecycle: sandbox produced no changes for %s", sandbox_root
            )
            return

        # Collect intended target paths. Porcelain v1 format is "XY path"
        # but GitService.status_porcelain strips the wrapping stdout, which
        # eats the leading space of the first line when X (staged) is
        # unmodified — so " M foo" arrives as "M foo". Split on first
        # whitespace to recover {status_token, path} regardless.
        target_paths: set[str] = set()
        for line in porcelain.splitlines():
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            status_token, rel = parts[0], parts[1].strip().strip('"')
            if "D" in status_token:
                logger.warning(
                    "SandboxLifecycle: sandbox reports deletion of %s — "
                    "atomic actions cannot delete files (#451); skipping",
                    rel,
                )
                continue
            target_paths.add(rel)

        if not target_paths:
            return

        # Conflict check: is the main tree dirty on any target path?
        try:
            main_porcelain = self.core_context.git_service.status_porcelain()
        except Exception as exc:
            logger.error(
                "SandboxLifecycle: main tree status read failed (%s); "
                "refusing to propagate without a conflict check",
                exc,
            )
            raise RuntimeError(
                f"ADR-071 D2.2: cannot verify main tree cleanliness ({exc}); "
                "refusing to propagate sandbox changes"
            ) from exc

        main_dirty: set[str] = set()
        for line in main_porcelain.splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2:
                main_dirty.add(parts[1].strip().strip('"'))

        conflict = sorted(target_paths & main_dirty)
        if conflict:
            raise RuntimeError(
                "ADR-071 D2.2: refusing to propagate sandbox changes — "
                f"main tree has uncommitted changes in {len(conflict)} "
                f"sandbox target file(s): {conflict[:5]}"
                f"{' ...' if len(conflict) > 5 else ''}. "
                "Commit or revert those changes, then re-run."
            )

        copied = 0
        for rel in sorted(target_paths):
            src = sandbox_root / rel
            if not src.exists():
                logger.warning(
                    "SandboxLifecycle: sandbox entry %s missing on disk; skipping",
                    rel,
                )
                continue
            file_handler.write_validated_bytes(rel, src.read_bytes())
            copied += 1

        logger.info(
            "SandboxLifecycle: propagated %d file(s) from sandbox to main tree",
            copied,
        )
