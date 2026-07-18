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
from body.atomic.sandbox_lifecycle import SandboxLifecycle
from body.flows.executor import FlowExecutor
from body.flows.registry import StepKind, flow_registry
from body.flows.result import declared_production
from body.services.service_registry import service_registry
from mind.governance.violation_report import extract_error_data
from shared.exceptions import GovernanceInstrumentError
from shared.infrastructure.intent.vocabulary_projection import (
    VocabularyProjectionError,
    load_vocabulary_projection,
)
from shared.logger import getLogger
from shared.protocols.cognitive_flow_delegate import CognitiveFlowDelegate
from will.autonomy.proposal import ProposalStatus
from will.autonomy.proposal_execution_pipeline import (
    CommitOutcome,
    capture_git_sha,
    commit_proposal_changes,
    compute_changed_files,
    compute_production_set,
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
                    "lifecycle_status": "failed",
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
                    "lifecycle_status": "failed",
                    "error": error,
                    "proposal_id": proposal.proposal_id,
                    "status": proposal.status.value,
                    "duration_sec": time.time() - start_time,
                }

            # ADR-101 D4: pre-claim scope-collision check (ADR-021 D5) is
            # retired. Content scope is enforced by construction in
            # commit_proposal_changes via the action's production set;
            # the path-shaped pre-claim guard contributed no remaining
            # safety property once the commit-set derivation moved off
            # proposal.scope.files.

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
                        "lifecycle_status": "failed",
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
            # #812: distinct from `ok` — `ok` historically meant "no action/
            # commit failure", which is a defensible contract for a
            # synchronous, human-triggered caller (proposal_runner.py /
            # proposals_routes.py) but was WRONG for ProposalConsumerWorker,
            # which needs to know whether the durable proof state (ADR-148
            # COMPLETED) was actually reached before running success effects.
            # lifecycle_status carries that distinction without changing
            # `ok`'s existing meaning for other callers. Default covers the
            # write=False (dry-run) path, which never reaches the write block
            # below.
            lifecycle_status = "dry_run"

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

                    flow_target_paths: set[str] | None = None
                    if ref_kind == "flow":
                        # ADR-106: a flow's steps build on one another (one writes
                        # a file, the next edits it, the last executes it), so the
                        # whole flow runs in ONE hermetic worktree — not per step.
                        # Mutations land in the sandbox; on flow success we
                        # propagate the production set back to the main tree
                        # (ADR-101 D2), and on failure the worktree is discarded so
                        # the main tree is never touched. Closes #629's
                        # blast-radius + no-rollback symptoms at the root: flow
                        # proposals previously skipped the sandbox single actions
                        # have had since ADR-071 D2.2.
                        sandbox = SandboxLifecycle(self.core_context)
                        scoped_context, scoped_git = (
                            sandbox.build_flow_execution_context(
                                ref_id, write, pre_execution_sha
                            )
                        )
                        try:
                            cognitive_delegate = self._build_cognitive_delegate(
                                ref_id, scoped_context
                            )
                            flow_executor = FlowExecutor(
                                scoped_context,
                                cognitive_delegate=cognitive_delegate,
                            )
                            result = await flow_executor.execute(
                                flow_id=ref_id,
                                write=write,
                                **params,
                            )
                            if scoped_git is not None and result.ok:
                                # ADR-107 D1/D3/D4: a flow commits its steps'
                                # DECLARED production (files_produced), not the
                                # worktree diff — so incidental fix.* churn stays
                                # sandbox-local. When no step declares production,
                                # only_paths stays None and propagate falls back
                                # to the full diff (D4, un-migrated flows).
                                declared = declared_production(result)
                                flow_target_paths = sandbox.propagate_changes(
                                    scoped_git, only_paths=declared
                                )
                        finally:
                            if scoped_git is not None:
                                scoped_git.cleanup()
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

                    result_data = (
                        result.data
                        if isinstance(result.data, dict)
                        else {"result": str(result.data)}
                    )
                    if flow_target_paths:
                        # ADR-106 D2: stamp the flow sandbox production set so
                        # compute_production_set drives the commit set (ADR-101
                        # D2). FlowResult.data is a computed property, so the
                        # persisted action_results entry is stamped, not
                        # result.data (which would not survive the property).
                        result_data = {
                            **result_data,
                            "_sandbox_target_paths": sorted(flow_target_paths),
                        }

                    action_results[f"{ref_id}:{action.order}"] = {
                        "ok": result.ok,
                        "duration_sec": action_duration,
                        "data": result_data,
                        "order": action.order,
                        "kind": ref_kind,
                    }

                    if not result.ok:
                        all_ok = False
                        logger.warning(
                            "%s %s failed: %s — stopping execution",
                            ref_kind.capitalize(),
                            ref_id,
                            (result.data or {}).get("error", "Unknown error"),
                        )
                        break
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
                        "Exception executing %s %s: %s — stopping execution",
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
                    break

            # 5. Update final status
            total_duration = time.time() - start_time

            if write:
                if all_ok:
                    # ADR-129 D7 / ADR-148 D3: commit before mark_completed.
                    # A refused (contamination) OR failed commit routes to
                    # mark_failed + rollback — never a completed row with no
                    # git record. Only a real commit or a legitimately-empty
                    # production set proceeds toward completion.
                    commit_outcome = commit_proposal_changes(
                        git_service=self.core_context.git_service,
                        proposal_id=proposal.proposal_id,
                        proposal_goal=proposal.goal,
                        action_results=action_results,
                    )

                    if commit_outcome in (
                        CommitOutcome.REFUSED_CONTAMINATION,
                        CommitOutcome.FAILED,
                    ):
                        all_ok = False
                        lifecycle_status = "failed"
                        if commit_outcome == CommitOutcome.REFUSED_CONTAMINATION:
                            reason = (
                                "ADR-129 D1: staging contamination detected — "
                                "commit refused to prevent authorship violation"
                            )
                        else:
                            reason = (
                                "ADR-148 D3: git commit failed — proposal not "
                                "completed to avoid a completed row with no git record"
                            )
                        failure_reason = reason
                        rollback_proposal(
                            git_service=self.core_context.git_service,
                            proposal_id=proposal.proposal_id,
                            action_results=action_results,
                            pre_sha=pre_execution_sha,
                        )
                        await state_manager.mark_failed(
                            proposal.proposal_id,
                            reason=reason,
                            results=action_results,
                        )
                        logger.error(
                            "Proposal %s failed: %s (%.2fs)",
                            proposal.proposal_id,
                            reason,
                            total_duration,
                        )
                    else:
                        # ADR-148 D2: commit succeeded -> FINALIZING. Record the
                        # evidence, then advance to COMPLETED only once the
                        # consequence chain is durable. A crash in this window
                        # leaves a recoverable FINALIZING row, never a false
                        # COMPLETED.
                        await state_manager.mark_finalizing(
                            proposal.proposal_id,
                            results=action_results,
                        )

                        # -- Consequence recording --
                        # Delegated to ConsequenceLogService (Body layer).
                        post_execution_sha = capture_git_sha(
                            self.core_context.git_service,
                            phase="post",
                            proposal_id=proposal.proposal_id,
                        )

                        changed_files = await compute_changed_files(
                            git_service=self.core_context.git_service,
                            pre_sha=pre_execution_sha,
                            post_sha=post_execution_sha,
                            proposal_id=proposal.proposal_id,
                        )

                        consequence_ok = await record_consequence(
                            proposal_id=proposal.proposal_id,
                            pre_sha=pre_execution_sha,
                            post_sha=post_execution_sha,
                            changed_files=changed_files,
                            finding_ids=proposal.constitutional_constraints.get(
                                "finding_ids", []
                            ),
                            policies=proposal.scope.policies,
                            declared_production=compute_production_set(action_results),
                        )
                        findings_ok = await resolve_deferred_findings(
                            proposal.proposal_id
                        )

                        # ADR-148 D1: COMPLETED only once the consequence chain is
                        # durable and the deferred findings are adjudicated.
                        if consequence_ok and findings_ok:
                            await state_manager.mark_completed(proposal.proposal_id)
                            lifecycle_status = "completed"
                            logger.info(
                                "Proposal completed successfully: %s (%.2fs)",
                                proposal.proposal_id,
                                total_duration,
                            )
                        else:
                            # #812: was previously indistinguishable from
                            # "completed" in the return value — all_ok stayed
                            # True here, so callers (ProposalConsumerWorker)
                            # counted this as succeeded and ran success
                            # effects for a proposal that never reached the
                            # durable proof state. lifecycle_status makes the
                            # distinction load-bearing without changing `ok`'s
                            # existing meaning for other callers.
                            lifecycle_status = "finalizing"
                            logger.warning(
                                "Proposal %s left FINALIZING (consequence=%s "
                                "findings=%s) — evidence not yet durable; the "
                                "stuck-finalizing reaper will re-drive it "
                                "(ADR-148 D4).",
                                proposal.proposal_id,
                                consequence_ok,
                                findings_ok,
                            )

                else:
                    lifecycle_status = "failed"
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
                        action_results=action_results,
                        pre_sha=pre_execution_sha,
                    )
            else:
                logger.info("DRY-RUN complete - no status updates")

            # 6. Return results
            return {
                "ok": all_ok,
                "lifecycle_status": lifecycle_status,
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

    def _build_cognitive_delegate(
        self,
        flow_id: str,
        scoped_context: Any,
    ) -> CognitiveFlowDelegate | None:
        """
        Return the appropriate CognitiveFlowDelegate for this flow, or None.

        Routes by cognitive_capability declared in the flow manifest (ADR-140 D9).
        generation_mode governs strategy inside the delegate, not which delegate
        to construct.
        """
        from will.agents.test_gen_cognitive_delegate import TestGenCognitiveDelegate

        flow_def = flow_registry.get(flow_id)
        if not flow_def:
            return None

        has_cognitive = any(s.kind == StepKind.COGNITIVE for s in flow_def.steps)
        if not has_cognitive:
            return None

        cap = flow_def.cognitive_capability
        if cap == "test_generation":
            return TestGenCognitiveDelegate(scoped_context)

        logger.error(
            "ProposalExecutor: no delegate registered for cognitive_capability=%r "
            "in flow %r — cognitive steps will fail at runtime",
            cap,
            flow_id,
        )
        return None
