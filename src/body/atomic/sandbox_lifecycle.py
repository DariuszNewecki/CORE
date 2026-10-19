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
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from body.atomic.registry import ActionDefinition
from shared.action_types import ActionImpact
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)

# ADR-071 D2.2 Phase 2: action impacts that warrant hermetic worktree
# sandboxing. WRITE_DATA is intentionally excluded — worktree isolation
# is a source-tree mechanism (git checkout of an isolated branch); it
# does nothing for database rows or external API calls.
#
# All currently-registered WRITE_DATA actions target internal systems:
#   - core DB writes (proposals, action_results, blackboard, sync)
#   - repo-local file ops persisted through var/ or test runners
# These are already governed by the proposal/claim system, which
# provides the compensating-action contract for DB mutations (#708).
#
# New WRITE_DATA actions targeting external systems (object stores,
# third-party APIs) MUST implement action-level pre-flight checks and
# compensation logic — sandbox exclusion is not a substitute for that.
_SANDBOXED_IMPACTS = frozenset({ActionImpact.WRITE_CODE, ActionImpact.WRITE_METADATA})


def _missing_parent_dirs(root: Path, rel_paths: Iterable[str]) -> list[str]:
    """Repo-relative parent directories of *rel_paths* that do not exist yet,
    deepest first, so a rollback can remove the ones a write created."""
    missing: set[str] = set()
    for rel in rel_paths:
        for parent in Path(rel).parents:
            if str(parent) in ("", ".") or (root / parent).exists():
                break
            missing.add(parent.as_posix())
    return sorted(missing, key=lambda d: d.count("/"), reverse=True)


def _roll_back(
    file_handler: Any,
    root: Path,
    touched: list[str],
    originals: dict[str, bytes | None],
    new_dirs: list[str],
) -> None:
    """Return every touched path to its snapshot bytes (F3).

    A path that did not exist is removed; one that did is rewritten with its
    original bytes; one already equal to its snapshot is left alone. Each
    restore is attempted even if another fails, and a failed restore is
    logged loudly — the caller re-raises the original error either way.
    """
    for rel in reversed(touched):
        path = root / rel
        original = originals.get(rel)
        try:
            current = path.read_bytes() if path.is_file() else None
            if current == original:
                continue
            if original is None:
                file_handler.remove_file(rel)
            else:
                file_handler.write(rel, original)
        except Exception as exc:
            logger.error(
                "SandboxLifecycle: rollback of %s FAILED (%s); main tree may "
                "differ from its pre-propagation state at this path",
                rel,
                exc,
            )
    for rel_dir in new_dirs:
        abs_dir = root / rel_dir
        try:
            if abs_dir.is_dir() and not any(abs_dir.iterdir()):
                file_handler.remove_tree(rel_dir)
        except Exception as exc:
            logger.error(
                "SandboxLifecycle: rollback could not remove new directory %s (%s)",
                rel_dir,
                exc,
            )


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

    Four public methods:

    - `build_execution_context` — decide whether to sandbox the about-to-run
      action, and if so produce a scoped CoreContext with `git_service`,
      `file_handler`, and `file_service` repointed at a fresh ScopedGitService
      worktree (#815 — every filesystem-facing service must agree on the same
      repo root; a mismatch splits writes across the worktree and main tree).

    - `build_flow_execution_context` — the flow-granularity counterpart.

    - `propagate_changes` — after a successful sandboxed run, copy the
      worktree's modified/untracked files back to the main tree through
      the unified `FileHandler.write` channel, with a conflict check that
      refuses to overwrite uncommitted main-tree changes (loud-failure
      contract).

    - `checkpoint_paths` / `restore_paths` (#814-adjacent) — snapshot and
      undo a caller's own multi-step write *within* one worktree, for a
      caller that runs several governed steps against the same worktree
      (e.g. one per symbol) and needs a later step's failure to roll back
      only that step's writes without discarding earlier steps' successes.
      Uses `scoped_context.file_handler` internally so Will-tier callers —
      whose sanctioned write door is `file_service`, not `file_handler` —
      never need to touch `file_handler` (or, for deletion, an escape hatch
      `file_service` doesn't even expose) directly themselves.

    All four are pure delegations of subsystem state — they share no
    in-flight state between calls. ActionExecutor/FlowExecutor callers hold
    the instance and drive the relevant call sites within a single
    `execute()` invocation, passing the `scoped_git`/`scoped_context` handle
    between them.
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
        self.core_context with `git_service`, `file_handler`, and
        `file_service` all repointed at a fresh ScopedGitService rooted
        at `pre_execution_sha` (#815 — all filesystem-facing services
        must agree on the same repo root). The caller MUST call
        `scoped_git.cleanup()` in a finally block.

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
        applies the context is a scoped copy with ``git_service``,
        ``file_handler``, and ``file_service`` all repointed at a fresh worktree
        at ``pre_execution_sha`` (#815). The caller MUST ``scoped_git.cleanup()``
        in a finally block and, on flow success, call
        ``propagate_changes(scoped_git)``.

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
        from body.infrastructure.storage.file_handler import FileHandler
        from body.services.file_service import FileService

        scoped_git = self.core_context.git_service.create_worktree(pre_execution_sha)
        try:
            scoped_file_handler = FileHandler(str(scoped_git.repo_path))
            # #815: file_handler and file_service are two independent
            # filesystem-facing services on CoreContext (shared.context) —
            # FileService binds its own internal FileHandler permanently to
            # whatever repo_path it is constructed with. Leaving file_service
            # unscoped here left a scoped CoreContext with a split-brain
            # filesystem: file_handler pointed at the worktree, file_service
            # still pointed at the main tree, so consumers that write via
            # file_service (e.g. PytestAcceptanceCondition) silently wrote
            # into the real repo instead of the sandbox.
            scoped_file_service = FileService(scoped_git.repo_path)
        except Exception:
            scoped_git.cleanup()
            raise

        scoped_context = dataclasses.replace(
            self.core_context,
            git_service=scoped_git,
            file_handler=scoped_file_handler,
            file_service=scoped_file_service,
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
        self,
        scoped_git: Any,
        only_paths: set[str] | None = None,
        declared_deletions: set[str] | None = None,
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
        FileHandler's unified ``write`` entry (ADR-097): bytes content skips
        every source-shape transform, so the copy is byte-identical — no
        re-syntax-check, no auto-newline injection. Each declared deletion
        goes through ``remove_file`` instead.

        Before copying anything, checks the main tree for uncommitted
        modifications in the sandbox's target paths. If any overlap, raises
        — the exception bubbles into execute()'s outer try and turns the
        action result into a loud failure, rather than silently overwriting
        the governor's concurrent edits. This is the safety mechanism the
        ADR-071 D2.2 plan describes as "loud failure rather than silent
        contamination". The b11f4dba race shape is closed: worker either
        propagates cleanly (no overlap) or refuses (overlap detected).

        It also refuses when the main tree's HEAD has moved since the sandbox
        was created and a commit in between touched a target path. The copy
        writes whole files built on the sandbox's base, so it would silently
        undo that commit; a clean tree does not prove nothing changed.
        Commits that touch none of the target paths leave those files identical
        in both trees, so they do not block.

        Deletions propagate only when the action declared them
        (``declared_deletions``, from the action's result) AND the sandbox
        shows them: the path is removed from the main tree through
        ``FileHandler.remove_file`` (the governed delete surface) and is part
        of the returned production set, so the commit carries the removal.
        ADR-168 Amendment 2026-10-10 A3: a patch's deleted files are applied
        and committed. An undeclared sandbox deletion is still logged and
        skipped — an action never deletes from the main tree by accident.

        The copy is all or nothing (F3): if any write or delete raises, every
        path already touched is restored to its pre-propagation bytes (new
        files and the directories they created are removed) and the error is
        re-raised, so the caller reports failure on an unchanged main tree.
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
        deletions: set[str] = set()
        allowed_deletions = declared_deletions or set()
        for line in porcelain.splitlines():
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            status_token, rel = parts[0], parts[1].strip().strip('"')
            if "D" in status_token:
                if rel in allowed_deletions:
                    deletions.add(rel)
                    target_paths.add(rel)
                else:
                    logger.warning(
                        "SandboxLifecycle: sandbox reports undeclared deletion "
                        "of %s; skipping",
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

        self._refuse_if_main_moved_under_targets(scoped_git, target_paths)

        # F3: all or nothing. Snapshot the main tree's bytes for every target
        # before the first write; a failure on any file restores the files
        # already replaced, removes the ones newly created, and re-raises —
        # the main tree is never left half-propagated.
        main_root = file_handler.repo_path
        originals = {
            rel: (main_root / rel).read_bytes() if (main_root / rel).is_file() else None
            for rel in target_paths
        }
        new_dirs = _missing_parent_dirs(main_root, target_paths)
        touched: list[str] = []
        copied = 0
        try:
            for rel in sorted(target_paths):
                touched.append(rel)
                if rel in deletions:
                    file_handler.remove_file(rel)
                    continue
                src = sandbox_root / rel
                if not src.exists():
                    logger.warning(
                        "SandboxLifecycle: sandbox entry %s missing on disk; skipping",
                        rel,
                    )
                    continue
                file_handler.write(rel, src.read_bytes())
                copied += 1
        except Exception as exc:
            logger.error(
                "SandboxLifecycle: propagation failed at %s (%s); rolling back "
                "%d file(s) in the main tree",
                touched[-1] if touched else "?",
                exc,
                len(touched),
            )
            _roll_back(file_handler, main_root, touched, originals, new_dirs)
            raise

        logger.info(
            "SandboxLifecycle: propagated %d file(s) and %d deletion(s) from "
            "sandbox to main tree",
            copied,
            len(deletions & target_paths),
        )
        return target_paths

    def _refuse_if_main_moved_under_targets(
        self, scoped_git: Any, target_paths: set[str]
    ) -> None:
        """Raise when a commit landed on the main tree after the sandbox's base
        and touched a target path. Fails closed when either HEAD or the
        commit range cannot be read."""
        try:
            sandbox_base = scoped_git.get_current_commit()
            main_head = self.core_context.git_service.get_current_commit()
            if sandbox_base == main_head:
                return
            moved = self.core_context.git_service.commits_between(
                sandbox_base, main_head
            )
        except Exception as exc:
            raise RuntimeError(
                "ADR-071 D2.2: cannot compare the main tree's HEAD with the "
                f"sandbox's base ({exc}); refusing to propagate sandbox changes"
            ) from exc

        touched = sorted(
            {path for _, _, paths in moved for path in paths} & target_paths
        )
        if touched:
            raise RuntimeError(
                "ADR-071 D2.2: refusing to propagate sandbox changes — the main "
                f"tree moved from {sandbox_base[:8]} to {main_head[:8]} and "
                f"{len(touched)} sandbox target file(s) changed in between: "
                f"{touched[:5]}{' ...' if len(touched) > 5 else ''}. Copying "
                "would undo those commits; re-run against the new HEAD."
            )

    # ID: 85d80659-74d3-47c7-bbd1-d51a6abf4527
    def checkpoint_paths(
        self, scoped_context: CoreContext, rel_paths: Iterable[str]
    ) -> dict[str, str | None]:
        """Snapshot the current content of each path inside a scoped worktree.

        Read-only. Returns `{rel_path: content_or_None}` — `None` means the
        path did not exist at checkpoint time. Pair with `restore_paths` to
        undo a caller's own multi-step write within one worktree when a
        later step fails and the earlier steps' writes must not survive
        (e.g. #817-adjacent: a per-symbol write inside a shared worktree
        whose later validation step fails must not leak into what a
        *different*, later-succeeding symbol propagates).
        """
        worktree_root = scoped_context.git_service.repo_path
        snapshot: dict[str, str | None] = {}
        for rel in rel_paths:
            path = worktree_root / rel
            snapshot[rel] = path.read_text(encoding="utf-8") if path.exists() else None
        return snapshot

    # ID: fb9c1231-70f7-422f-a1cb-ad57b2742852
    def restore_paths(
        self, scoped_context: CoreContext, snapshot: dict[str, str | None]
    ) -> None:
        """Restore each checkpointed path to its pre-checkpoint state.

        Rewrites the checkpointed content where it existed, removes the
        path where it did not (via `file_handler.remove_file` — the
        sanctioned Body-tier deletion surface; Will-tier callers MUST NOT
        reach for raw file_handler/unlink themselves, which is exactly the
        boundary violation this method exists to avoid — CoreContext
        documents `file_service` as the Will-tier write door and reserves
        `file_handler` for Body/infrastructure). A path whose current
        content already matches its checkpoint is left untouched (no-op
        write). Uses `scoped_context.file_handler` — the scoped, worktree-
        rooted handler — never the main tree's.
        """
        worktree_root = scoped_context.git_service.repo_path
        for rel, checkpointed_content in snapshot.items():
            path = worktree_root / rel
            current = path.read_text(encoding="utf-8") if path.exists() else None
            if current == checkpointed_content:
                continue
            if checkpointed_content is None:
                scoped_context.file_handler.remove_file(rel)
            else:
                scoped_context.file_handler.write(rel, checkpointed_content)
