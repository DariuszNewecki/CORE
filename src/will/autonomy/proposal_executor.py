# src/will/autonomy/proposal_executor.py
"""
Proposal Executor - Execute approved proposals through ActionExecutor

Bridge between A3 proposals and the action execution system.

CONSTITUTIONAL (current):
- Will orchestrates execution flow.
- DB session acquisition is delegated to ServiceRegistry (in Body).
- ProposalRepository remains the DB abstraction for proposal persistence.
- This module does NOT import AsyncSession (architectural boundary).
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from body.atomic.executor import ActionExecutor
from body.flows.executor import FlowExecutor
from body.services.service_registry import service_registry
from mind.governance.violation_report import extract_error_data
from shared.exceptions import GovernanceInstrumentError
from shared.infrastructure.intent.autonomy_dirty_tree import (
    load_autonomy_dirty_tree_policy,
)
from shared.infrastructure.intent.vocabulary_projection import (
    VocabularyProjectionError,
    load_vocabulary_projection,
)
from shared.logger import getLogger
from will.autonomy.proposal import ProposalStatus
from will.autonomy.proposal_execution_pipeline import (
    capture_git_sha,
    commit_proposal_changes,
    compute_changed_files,
    record_consequence,
    resolve_deferred_findings,
    rollback_proposal,
)
from will.autonomy.proposal_repository import ProposalRepository
from will.autonomy.proposal_state_manager import ProposalStateManager


logger = getLogger(__name__)


# ID: 69e9d2f1-3246-4a09-a5a8-fc0e1e882f47
class ProposalExecutor:
    """
    Executes approved proposals through ActionExecutor.

    Constitutional Note:
    - No AsyncSession import here (boundary rule).
    - Session is acquired via service_registry.session() (Body-owned mechanism).
    """

    def __init__(self, core_context):
        self.core_context = core_context
        self.action_executor = ActionExecutor(core_context)
        logger.debug("ProposalExecutor initialized")

    async def _check_scope_collision(self, proposal) -> dict | None:
        """
        Pre-claim scope-collision check per ADR-021 D5.

        Returns a yield result dict if the dirty working tree intersects
        proposal.scope.files (or, under any_dirty mode, if the working
        tree is dirty at all). Returns None if it is safe to proceed.

        Mode is read from .intent/enforcement/config/autonomy_dirty_tree.yaml.
        On loader sentinel, treats mode as any_dirty (conservative halt).
        """
        if self.core_context.git_service is None:
            return None

        policy = load_autonomy_dirty_tree_policy()
        if policy.get("_error"):
            logger.warning(
                "autonomy_dirty_tree policy unavailable (%s) — defaulting to any_dirty",
                policy.get("reason"),
            )
            mode = "any_dirty"
        else:
            mode = policy["mode"]

        try:
            porcelain = self.core_context.git_service.status_porcelain()
        except RuntimeError as status_err:
            logger.warning(
                "Could not read working-tree status — proceeding cautiously: %s",
                status_err,
            )
            return None

        dirty_paths: set[str] = set()
        for line in porcelain.splitlines():
            if len(line) < 4:
                continue
            path = line[3:]
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            if path:
                dirty_paths.add(path)

        if not dirty_paths:
            return None

        scope_files = set(proposal.scope.files)
        intersection = dirty_paths & scope_files

        if mode == "any_dirty" or intersection:
            colliding = (
                sorted(intersection)
                if mode == "intersection_only"
                else sorted(dirty_paths)
            )
            return {
                "ok": False,
                "yielded": True,
                "yield_reason": "scope_collision"
                if mode == "intersection_only"
                else "any_dirty",
                "colliding_paths": colliding,
                "proposal_id": proposal.proposal_id,
                "duration_sec": 0.0,
            }

        return None

    # ID: 5bb8175a-6a30-4548-8597-977a43fcb0b7
    async def execute(
        self,
        proposal_id: str,
        claimed_by: UUID,
        write: bool = False,
    ) -> dict[str, Any]:
        start_time = time.time()

        # DEGRADED pre-check (ADR-023 D4): refuse to execute proposals while
        # the vocabulary projection is broken. Caller (ProposalConsumerWorker)
        # should treat this as blocked, not failed — re-queue when restored.
        projection = load_vocabulary_projection()
        if isinstance(projection, VocabularyProjectionError):
            raise GovernanceInstrumentError(
                instrument="vocabulary_projection",
                reason=projection.reason,
            )

        async with service_registry.session() as session:
            repo = ProposalRepository(session)

            # 1. Load proposal
            logger.info("Loading proposal: %s", proposal_id)
            proposal = await repo.get(proposal_id)

            if not proposal:
                error = f"Proposal not found: {proposal_id}"
                logger.error(error)
                return {
                    "ok": False,
                    "error": error,
                    "duration_sec": time.time() - start_time,
                }

            logger.info(
                "Loaded proposal: %s (status=%s, actions=%d)",
                proposal.proposal_id,
                proposal.status.value,
                len(proposal.actions),
            )

            # 2. Validate status
            if proposal.status != ProposalStatus.APPROVED:
                error = f"Proposal not approved (status={proposal.status.value})"
                logger.error(error)
                return {
                    "ok": False,
                    "error": error,
                    "proposal_id": proposal.proposal_id,
                    "status": proposal.status.value,
                    "duration_sec": time.time() - start_time,
                }

            # Pre-claim scope-collision check (ADR-021 D5)
            collision = await self._check_scope_collision(proposal)
            if collision is not None:
                logger.info(
                    "Proposal %s yielded pre-claim: %s (colliding=%d)",
                    proposal.proposal_id,
                    collision["yield_reason"],
                    len(collision["colliding_paths"]),
                )
                return collision

            # 3. Mark as executing via claim.proposal atomic action (only if write=True)
            if write:
                state_manager = ProposalStateManager(session)
                claim_result = await self.action_executor.execute(
                    "claim.proposal",
                    proposal_id=proposal.proposal_id,
                    claimed_by=claimed_by,
                    write=write,
                )
                if not claim_result.ok:
                    return {
                        "ok": False,
                        "error": (
                            f"claim.proposal failed: "
                            f"{claim_result.data.get('error', 'rowcount=0')}"
                        ),
                        "proposal_id": proposal.proposal_id,
                        "duration_sec": time.time() - start_time,
                    }
            else:
                logger.info("DRY-RUN mode - not updating proposal status")

            # Capture pre-execution HEAD so we can restore the working tree on failure.
            pre_execution_sha = capture_git_sha(
                self.core_context.git_service,
                phase="pre",
                proposal_id=proposal.proposal_id,
            )

            changed_files: list[str] = []
            post_execution_sha: str | None = None
            failure_reason: str | None = None

            # 4. Execute actions in order
            action_results: dict[str, Any] = {}
            all_ok = True

            sorted_actions = sorted(proposal.actions, key=lambda a: a.order)

            logger.info("Executing %d actions...", len(sorted_actions))

            for action in sorted_actions:
                action_start = time.time()
                ref_id = action.ref_id
                ref_kind = action.ref_kind

                logger.info(
                    "Executing %s %d/%d: %s",
                    ref_kind,
                    action.order + 1,
                    len(sorted_actions),
                    ref_id,
                )

                try:
                    params = {
                        k: v for k, v in action.parameters.items() if k != "write"
                    }

                    if ref_kind == "flow":
                        flow_executor = FlowExecutor(self.core_context)
                        result = await flow_executor.execute(
                            flow_id=ref_id,
                            write=write,
                            **params,
                        )
                    else:
                        # ADR-071 D2.2 Phase 2: thread pre_execution_sha so
                        # write-bearing actions execute in a hermetic worktree
                        # rooted at the SHA captured before the claim. The
                        # executor sandboxes only when impact is WRITE_CODE /
                        # WRITE_METADATA AND write=True; CLI direct invocations
                        # leave pre_execution_sha=None and pass through.
                        result = await self.action_executor.execute(
                            action_id=ref_id,
                            write=write,
                            pre_execution_sha=pre_execution_sha,
                            **params,
                        )

                    action_duration = time.time() - action_start

                    action_results[f"{ref_id}:{action.order}"] = {
                        "ok": result.ok,
                        "duration_sec": action_duration,
                        "data": result.data,
                        "order": action.order,
                        "kind": ref_kind,
                    }

                    if not result.ok:
                        all_ok = False
                        logger.warning(
                            "%s %s failed: %s",
                            ref_kind.capitalize(),
                            ref_id,
                            (result.data or {}).get("error", "Unknown error"),
                        )
                    else:
                        logger.info(
                            "%s %s completed successfully (%.2fs)",
                            ref_kind.capitalize(),
                            ref_id,
                            action_duration,
                        )

                except Exception as e:
                    action_duration = time.time() - action_start
                    all_ok = False

                    logger.error(
                        "Exception executing %s %s: %s",
                        ref_kind,
                        ref_id,
                        e,
                        exc_info=True,
                    )

                    action_results[f"{ref_id}:{action.order}"] = {
                        "ok": False,
                        "duration_sec": action_duration,
                        "data": extract_error_data(e, error_type=type(e).__name__),
                        "order": action.order,
                        "kind": ref_kind,
                    }

            # 5. Update final status
            total_duration = time.time() - start_time

            if write:
                if all_ok:
                    await state_manager.mark_completed(
                        proposal.proposal_id,
                        results=action_results,
                    )
                    logger.info(
                        "Proposal completed successfully: %s (%.2fs)",
                        proposal.proposal_id,
                        total_duration,
                    )
                    commit_proposal_changes(
                        git_service=self.core_context.git_service,
                        proposal_id=proposal.proposal_id,
                        proposal_goal=proposal.goal,
                        scope_files=proposal.scope.files,
                        action_results=action_results,
                    )

                    # -- Consequence recording --
                    # Delegated to ConsequenceLogService (Body layer).
                    post_execution_sha = capture_git_sha(
                        self.core_context.git_service,
                        phase="post",
                        proposal_id=proposal.proposal_id,
                    )

                    changed_files = await compute_changed_files(
                        repo_path=str(self.core_context.git_service.repo_path),
                        pre_sha=pre_execution_sha,
                        post_sha=post_execution_sha,
                        proposal_id=proposal.proposal_id,
                    )

                    await record_consequence(
                        proposal_id=proposal.proposal_id,
                        pre_sha=pre_execution_sha,
                        post_sha=post_execution_sha,
                        changed_files=changed_files,
                        finding_ids=proposal.constitutional_constraints.get(
                            "finding_ids", []
                        ),
                        policies=proposal.scope.policies,
                    )

                    await resolve_deferred_findings(proposal.proposal_id)

                else:
                    failed_actions = [
                        aid for aid, res in action_results.items() if not res["ok"]
                    ]
                    reason = f"Actions failed: {', '.join(failed_actions)}"
                    failure_reason = reason
                    await state_manager.mark_failed(
                        proposal.proposal_id, reason=reason, results=action_results
                    )
                    logger.error(
                        "Proposal failed: %s - %s", proposal.proposal_id, reason
                    )
                    rollback_proposal(
                        git_service=self.core_context.git_service,
                        proposal_id=proposal.proposal_id,
                        scope_files=proposal.scope.files,
                        pre_sha=pre_execution_sha,
                    )
            else:
                logger.info("DRY-RUN complete - no status updates")

            # 6. Return results
            return {
                "ok": all_ok,
                "proposal_id": proposal.proposal_id,
                "goal": proposal.goal,
                "write": write,
                "actions_executed": len(action_results),
                "actions_succeeded": sum(1 for r in action_results.values() if r["ok"]),
                "actions_failed": sum(
                    1 for r in action_results.values() if not r["ok"]
                ),
                "action_results": action_results,
                "changed_files": changed_files,
                "post_execution_sha": post_execution_sha,
                "failure_reason": failure_reason,
                "duration_sec": total_duration,
            }
