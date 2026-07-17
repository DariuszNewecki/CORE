# src/will/workers/proposal_consumer_worker.py
"""
ProposalConsumerWorker - A3 Autonomous Proposal Execution Worker.

Responsibility: Poll for APPROVED proposals, execute them via
ProposalExecutor, and post blackboard reports.

This is the A3 unlock — it closes the loop:
  ViolationRemediatorWorker creates proposals
      ↓
  ProposalConsumerWorker (THIS WORKER) executes them
      ↓
  AuditViolationSensor confirms violations resolved

Constitutional standing:
- Declaration:      .intent/workers/proposal_consumer_worker.yaml
- Class:            acting
- Phase:            execution
- Permitted tools:  crate.create, canary.validate, crate.apply, git.commit
- Approval:         false — only executes already-approved proposals

LAYER: will/workers — acting worker. Receives CoreContext via constructor.
All src/ writes delegated to ProposalExecutor → ActionExecutor → Crate → Canary.

The post-execution side-effects (forwarding action findings_to_post,
emitting `python::test.coverage::*` findings for changed src/*.py files,
posting scope-collision yields) live in proposal_consumer_effects.py. The §7a revival contract (revive deferred
findings + post revival report when a proposal terminates
non-successfully) lives in proposal_consumer_revival.py. The dispatch
shell below stays focused on polling, executor invocation, and run
accounting.
"""

from __future__ import annotations

from typing import Any

from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger
from shared.workers.base import Worker
from will.autonomy.proposal_consumer_effects import (
    apply_success_effects,
    summarize_flow_step_failures,
)
from will.autonomy.proposal_consumer_revival import (
    mark_proposal_failed,
    release_executing_proposals,
    revive_and_report,
)


logger = getLogger(__name__)

# Conservative — each proposal may touch multiple files
_CFG = load_operational_config().workers.proposal_consumer


# ID: aeb11b94-471b-4caf-a84f-faa28f0f40fd
class ProposalConsumerWorker(Worker):
    """
    Acting worker. Polls for APPROVED proposals and executes them via
    ProposalExecutor with write=True.

    Only executes proposals already in APPROVED status — it never approves
    anything itself. Proposals with approval_required=True must be approved
    by a human before this worker will touch them.

    Posts a blackboard report after each run with execution results.
    """

    declaration_name = "proposal_consumer_worker"

    def __init__(
        self, core_context: Any, declaration_name: str = "", **kwargs: Any
    ) -> None:
        super().__init__(declaration_name=declaration_name)
        self._ctx = core_context

    # ID: 362177ba-db94-496f-8f04-60074ec6014b
    async def run(self) -> None:
        """
        Poll for APPROVED proposals and execute them.

        1. Load approved proposals (up to _CFG.claim_limit)
        2. For each: execute via ProposalExecutor(write=True) and route
           the outcome to the appropriate post-execution collaborator
        3. Post blackboard report with results
        """
        await self.post_heartbeat()

        proposals = await self._load_approved_proposals()

        if not proposals:
            await self.post_report(
                subject="proposal_consumer_worker.run.complete",
                payload={"executed": 0, "message": "No approved proposals."},
            )
            logger.info("ProposalConsumerWorker: no approved proposals.")
            return

        logger.info(
            "ProposalConsumerWorker: %d approved proposals to execute.",
            len(proposals),
        )

        from will.autonomy.proposal_executor import ProposalExecutor

        executor = ProposalExecutor(self._ctx)

        succeeded = 0
        failed = 0
        pending = 0
        results: list[dict[str, Any]] = []

        try:
            for proposal in proposals:
                proposal_id = proposal["proposal_id"]
                goal = proposal["goal"]

                logger.info(
                    "ProposalConsumerWorker: executing proposal '%s' — %s",
                    proposal_id,
                    goal[:80],
                )

                try:
                    result = await executor.execute(
                        proposal_id, self.worker_uuid, write=True
                    )

                    # ADR-101 D4: ProposalExecutor no longer yields pre-claim
                    # on scope collision; result.get("yielded") is dead code.
                    # Content scope is enforced in commit_proposal_changes via
                    # the action's production set rather than path-shaped guards.

                    # #812: gate on lifecycle_status, not the bare `ok` flag.
                    # `ok` historically meant "no action/commit failure", which
                    # stayed True even when the proposal was left FINALIZING
                    # (commit succeeded but the consequence chain never became
                    # durable) — so this worker counted it as succeeded and
                    # ran success effects (test-coverage findings, forwarded
                    # action findings) for a proposal that never reached the
                    # ADR-148 proof state COMPLETED.
                    lifecycle_status = result.get("lifecycle_status")
                    if lifecycle_status == "completed":
                        succeeded += 1
                        logger.info(
                            "ProposalConsumerWorker: proposal '%s' succeeded "
                            "(%d actions, %.2fs)",
                            proposal_id,
                            result["actions_executed"],
                            result["duration_sec"],
                        )
                        await apply_success_effects(self, proposal_id, result)
                    elif lifecycle_status == "finalizing":
                        # Committed but not yet durable — neither success nor
                        # failure. The ADR-148 D4 stuck-finalizing reaper
                        # (ProposalPipelineShopManager) owns re-driving this;
                        # revive_and_report is NOT called here since the
                        # deferred findings are not actually failed, just not
                        # yet resolved, and reviving them would race the
                        # reaper's own ownership of the row.
                        pending += 1
                        logger.warning(
                            "ProposalConsumerWorker: proposal '%s' left "
                            "FINALIZING — commit succeeded but evidence is "
                            "not yet durable; the stuck-finalizing reaper "
                            "will re-drive it (ADR-148 D4).",
                            proposal_id,
                        )
                    else:
                        failed += 1
                        logger.warning(
                            "ProposalConsumerWorker: proposal '%s' failed — %s",
                            proposal_id,
                            result.get("error", "unknown"),
                        )
                        # §7a orchestration: mark_failed has already run inside
                        # executor.execute() and transitioned the proposal row.
                        # Revival + revival report posted via the collaborator
                        # (UPDATE-only service call + Worker-attributed post per
                        # ADR-011).
                        reason = (
                            result.get("failure_reason") or "proposal execution failed"
                        )
                        await revive_and_report(self, proposal_id, reason)

                    # ADR-046 D3b: surface optional flow-step failures (e.g.
                    # silent fix.format failures inside flow.build_tests) in
                    # the run.complete report so they are discoverable without
                    # introducing a new finding subject family.
                    flow_step_failures = summarize_flow_step_failures(
                        result.get("action_results")
                    )
                    results.append(
                        {
                            "proposal_id": proposal_id,
                            "goal": goal,
                            "ok": result["ok"],
                            "lifecycle_status": lifecycle_status,
                            "actions_executed": result.get("actions_executed", 0),
                            "actions_succeeded": result.get("actions_succeeded", 0),
                            "actions_failed": result.get("actions_failed", 0),
                            "duration_sec": result.get("duration_sec", 0),
                            "error": result.get("error"),
                            "flow_step_failures": flow_step_failures,
                        }
                    )

                except Exception as e:
                    failed += 1
                    logger.error(
                        "ProposalConsumerWorker: exception executing '%s': %s",
                        proposal_id,
                        e,
                        exc_info=True,
                    )
                    # The executor raised before its internal mark_failed could
                    # run, so we transition the row ourselves and then run the
                    # same revival sequence as the ok=False branch.
                    await mark_proposal_failed(proposal_id, str(e))
                    await revive_and_report(self, proposal_id, str(e))

                    results.append(
                        {
                            "proposal_id": proposal_id,
                            "goal": goal,
                            "ok": False,
                            "lifecycle_status": "failed",
                            "error": str(e),
                        }
                    )

        finally:
            # Release any proposals still in EXECUTING status owned by this
            # worker. Handles graceful-shutdown paths (SIGTERM → CancelledError,
            # unhandled BaseException) that bypass the per-proposal except block.
            released = await release_executing_proposals(self, self.worker_uuid)
            if released:
                logger.warning(
                    "ProposalConsumerWorker: released %d stuck proposal(s) on shutdown",
                    released,
                )

        await self.post_report(
            subject="proposal_consumer_worker.run.complete",
            payload={
                "executed": len(results),
                "succeeded": succeeded,
                "failed": failed,
                "pending": pending,
                "results": results,
                "message": (
                    f"{succeeded} proposals executed, {failed} failed, "
                    f"{pending} left finalizing (ADR-148 D4 reaper owns them)."
                ),
            },
        )

        logger.info(
            "ProposalConsumerWorker: %d succeeded, %d failed, %d finalizing.",
            succeeded,
            failed,
            pending,
        )

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------

    async def _load_approved_proposals(self) -> list[dict[str, Any]]:
        """
        Load up to _CFG.claim_limit proposals in APPROVED status.
        Returns minimal dicts: proposal_id, goal.
        """
        from body.services.service_registry import service_registry
        from will.autonomy.proposal import ProposalStatus
        from will.autonomy.proposal_repository import ProposalRepository

        try:
            async with service_registry.session() as session:
                repo = ProposalRepository(session)
                proposals = await repo.list_by_status(
                    ProposalStatus.APPROVED, limit=_CFG.claim_limit
                )
                return [
                    {"proposal_id": p.proposal_id, "goal": p.goal} for p in proposals
                ]
        except Exception as e:
            logger.error(
                "ProposalConsumerWorker: failed to load approved proposals: %s", e
            )
            return []
