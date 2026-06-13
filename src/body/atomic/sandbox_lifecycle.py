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
only through the unified FileHandler.write channel (ADR-097 step 6,
which retired the previous write_validated_bytes carveout — the
sandbox-already-validated content survives a second pass through the
repo-source IntentGuard tier idempotently).
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


def _flow_has_sandboxable_step(
    flow_id: str, _visited: frozenset[str] = frozenset()
) -> bool:
    """True if a flow contains ≥1 write-bearing action step (ADR-106 D5).

    Resolves each ACTION step's declared @atomic_action impact and returns
    True as soon as one is in ``_SANDBOXED_IMPACTS`` (WRITE_CODE/WRITE_METADATA),
    recursing through nested FLOW steps. Mirrors the per-action gate in
    ``build_execution_context`` but at flow granularity (ADR-046 D1 — a flow's
    impact is the max of its steps). Cycle-safe via ``_visited``; an
    unresolvable flow/action is treated as non-sandboxable (the conservative
    direction here is "don't create a worktree for a flow that writes nothing").
    """
    from body.atomic.registry import action_registry
    from body.flows.registry import StepKind, flow_registry

    if flow_id in _visited:
        return False
    visited = _visited | {flow_id}

    flow_def = flow_registry.get(flow_id)
    if flow_def is None:
        return False

    for step in flow_def.steps:
        if step.kind == StepKind.ACTION:
            definition = action_registry.get(step.ref_id)
            metadata = getattr(
                getattr(definition, "executor", None), "_atomic_action_metadata", None
            )
            if metadata is not None and metadata.impact in _SANDBOXED_IMPACTS:
                return True
        elif step.kind == StepKind.FLOW and _flow_has_sandboxable_step(
            step.ref_id, visited
        ):
            return True
    return False


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
      the unified `FileHandler.write` channel, with a conflict check that
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

        return self._make_scoped_context(pre_execution_sha, definition.action_id)

    # ID: 7e1a4d92-5c3b-4f08-a6d1-9b2e8c4f7a30
    def build_flow_execution_context(
        self,
        flow_id: str,
        write: bool,
        pre_execution_sha: str | None,
    ) -> tuple[CoreContext, Any]:
        """Decide whether to sandbox a whole-flow execution (ADR-106 D1).

        The flow-granularity counterpart to ``build_execution_context``. A flow's
        steps build on one another (one writes a file, the next edits it, the
        last executes it), so the unit of isolation is the *flow execution*, not
        the individual action — one worktree spans every step. Returns
        ``(context_to_pass_to_FlowExecutor, scoped_git_or_None)``; when sandboxing
        applies the context is a scoped copy with ``git_service`` and
        ``file_handler`` repointed at a fresh worktree at ``pre_execution_sha``.
        The caller MUST ``scoped_git.cleanup()`` in a finally block and, on
        flow success, call ``propagate_changes(scoped_git)``.

        Gate (all required, ADR-106 D5):
          - pre_execution_sha is not None (autonomous call path)
          - write is True
          - the flow contains ≥1 step whose action impact ∈
            {WRITE_CODE, WRITE_METADATA} (``_flow_has_sandboxable_step``)
        """
        if (
            pre_execution_sha is None
            or not write
            or self.core_context.git_service is None
        ):
            return self.core_context, None

        if not _flow_has_sandboxable_step(flow_id):
            return self.core_context, None

        return self._make_scoped_context(pre_execution_sha, flow_id)

    # ID: 4c8f1b6e-2d97-4a53-be0c-5f3a9d72e681
    def _make_scoped_context(
        self, pre_execution_sha: str, label: str
    ) -> tuple[CoreContext, Any]:
        """Create a worktree at ``pre_execution_sha`` and a scoped CoreContext.

        Shared core of ``build_execution_context`` (per action) and
        ``build_flow_execution_context`` (per flow): both gate on their own
        conditions, then build an identical hermetic worktree. ``label`` is the
        action_id or flow_id, used only for the log line. The caller MUST call
        ``scoped_git.cleanup()`` in a finally block.
        """
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
            label,
            scoped_git.repo_path,
            pre_execution_sha[:12],
        )
        return scoped_context, scoped_git

    # ID: b1d2c5f9-3a48-4e67-8b91-2c5f8a3d6e90
    def propagate_changes(
        self, scoped_git: Any, only_paths: set[str] | None = None
    ) -> set[str]:
        """Copy files modified inside the sandbox back to the main tree.

        Returns the set of paths the sandbox observed as modified or
        untracked (i.e. the sandbox's production set for this action).
        Per ADR-101 D2 the caller (ActionExecutor) stamps this set onto
        the returned ActionResult so commit_proposal_changes derives the
        commit set from actual production rather than permission scope.
        Empty set is returned when the sandbox produced nothing or when
        the sandbox's own status read failed (loud-failure cases raise
        before reaching the return statement).

        ``only_paths`` (ADR-107 D3): when supplied, the copy-back is
        restricted to this allowlist — the worktree's observed changes are
        intersected with it, so files the sandbox changed *incidentally*
        (e.g. a formatter reformatting unrelated files) stay sandbox-local
        and are discarded with the worktree, never propagated. A declared
        path that the worktree did not actually change is a no-op, not a
        failure. The per-action path leaves ``only_paths=None`` and
        propagates its full diff (an action's only change is its output);
        the flow path supplies the union of its steps' ``files_produced``
        (ADR-107 D1).

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
            return set()

        if not porcelain:
            logger.debug(
                "SandboxLifecycle: sandbox produced no changes for %s", sandbox_root
            )
            return set()

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

        # ADR-107 D3: bound the production set to the declared-output allowlist.
        # Incidental sandbox churn (paths the worktree changed but no step
        # declared as produced) is dropped here — it is discarded with the
        # worktree, never reaching the main tree.
        if only_paths is not None:
            dropped = target_paths - only_paths
            target_paths &= only_paths
            if dropped:
                logger.info(
                    "SandboxLifecycle: discarding %d incidental sandbox change(s) "
                    "outside the declared production set (ADR-107)",
                    len(dropped),
                )

        if not target_paths:
            return set()

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
            file_handler.write(rel, src.read_bytes())
            copied += 1

        logger.info(
            "SandboxLifecycle: propagated %d file(s) from sandbox to main tree",
            copied,
        )
        return target_paths
