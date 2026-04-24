# src/will/workers/proposal_consumer_worker.py
# ID: will.workers.proposal_consumer_worker
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
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

_CLAIM_LIMIT = 5  # Conservative — each proposal may touch multiple files


# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
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

    # ID: b2c3d4e5-f6a7-8901-bcde-f12345678901
    async def run(self) -> None:
        """
        Poll for APPROVED proposals and execute them.

        1. Load approved proposals (up to _CLAIM_LIMIT)
        2. For each: execute via ProposalExecutor(write=True)
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
        results = []

        for proposal in proposals:
            proposal_id = proposal["proposal_id"]
            goal = proposal["goal"]

            logger.info(
                "ProposalConsumerWorker: executing proposal '%s' — %s",
                proposal_id,
                goal[:80],
            )

            try:
                result = await executor.execute(proposal_id, write=True)

                if result["ok"]:
                    succeeded += 1
                    logger.info(
                        "ProposalConsumerWorker: proposal '%s' succeeded "
                        "(%d actions, %.2fs)",
                        proposal_id,
                        result["actions_executed"],
                        result["duration_sec"],
                    )
                    # Post any finding_to_post entries declared by atomic actions.
                    # ADR-011: attribution flows through Worker.post_finding, not
                    # through raw SQL in the action body. Actions return
                    # finding_to_post in ActionResult.data; the Worker posts here.
                    # Runs before the changed_files loop so a downstream worker
                    # reacting to the posted finding sees it before any
                    # test.run_required entries for the same file.
                    action_results = result.get("action_results", {}) or {}
                    for aid, ar in action_results.items():
                        if not ar.get("ok"):
                            continue
                        ar_data = ar.get("data") or {}
                        finding_to_post = ar_data.get("finding_to_post")
                        if not finding_to_post:
                            continue
                        subject = finding_to_post.get("subject")
                        payload = finding_to_post.get("payload")
                        if not subject or payload is None:
                            logger.warning(
                                "Malformed finding_to_post from action %s "
                                "(missing subject/payload): %r",
                                aid,
                                finding_to_post,
                            )
                            continue
                        try:
                            await self.post_finding(subject=subject, payload=payload)
                            logger.info(
                                "ProposalConsumerWorker: posted finding %s from action %s",
                                subject,
                                aid,
                            )
                        except Exception as post_err:
                            logger.warning(
                                "Could not post finding_to_post from action %s: %s",
                                aid,
                                post_err,
                            )
                    # Post test.run_required for each changed source file.
                    # Attribution flows through the Worker base class — self.post_finding
                    # uses self._worker_uuid and self._phase, satisfying the
                    # blackboard_entries NOT NULL constraint that ProposalExecutor
                    # could not satisfy on its own.
                    changed_files = result.get("changed_files", []) or []
                    post_execution_sha = result.get("post_execution_sha")
                    for path in changed_files:
                        if path.startswith("src/") and path.endswith(".py"):
                            try:
                                await self.post_finding(
                                    subject=f"test.run_required::{path}",
                                    payload={
                                        "source_file": path,
                                        "proposal_id": proposal_id,
                                        "post_execution_sha": post_execution_sha,
                                    },
                                )
                            except Exception as test_req_err:
                                logger.warning(
                                    "Could not post test.run_required for proposal %s: %s",
                                    proposal_id,
                                    test_req_err,
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
                    # Worker now revives any findings that were deferred to
                    # this proposal (UPDATE-only service call) and posts the
                    # revival report with Worker attribution (ADR-011).
                    reason = result.get("failure_reason") or "proposal execution failed"
                    try:
                        from body.services.service_registry import service_registry

                        bb_service = await service_registry.get_blackboard_service()
                        revival = await bb_service.revive_findings_for_failed_proposal(
                            proposal_id=proposal_id,
                            failure_reason=reason,
                        )
                    except Exception as revive_err:
                        logger.warning(
                            "Revival query failed for proposal %s: %s",
                            proposal_id,
                            revive_err,
                        )
                        revival = None

                    if revival and revival.get("revived_count", 0) > 0:
                        try:
                            await self.post_report(
                                subject=f"proposal.failure.revival::{proposal_id}",
                                payload={
                                    "proposal_id": revival["proposal_id"],
                                    "failure_reason": revival["failure_reason"],
                                    "revived_count": revival["revived_count"],
                                    "revived_subjects": revival["revived_subjects"],
                                },
                            )
                            logger.info(
                                "ProposalConsumerWorker: posted revival report for "
                                "proposal %s (%d findings revived)",
                                proposal_id,
                                revival["revived_count"],
                            )
                        except Exception as post_err:
                            logger.warning(
                                "Failed to post revival report for proposal %s: %s",
                                proposal_id,
                                post_err,
                            )

                results.append(
                    {
                        "proposal_id": proposal_id,
                        "goal": goal,
                        "ok": result["ok"],
                        "actions_executed": result.get("actions_executed", 0),
                        "actions_succeeded": result.get("actions_succeeded", 0),
                        "actions_failed": result.get("actions_failed", 0),
                        "duration_sec": result.get("duration_sec", 0),
                        "error": result.get("error"),
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
                results.append(
                    {
                        "proposal_id": proposal_id,
                        "goal": goal,
                        "ok": False,
                        "error": str(e),
                    }
                )

        await self.post_report(
            subject="proposal_consumer_worker.run.complete",
            payload={
                "executed": len(results),
                "succeeded": succeeded,
                "failed": failed,
                "results": results,
                "message": f"{succeeded} proposals executed, {failed} failed.",
            },
        )

        logger.info(
            "ProposalConsumerWorker: %d succeeded, %d failed.",
            succeeded,
            failed,
        )

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------

    async def _load_approved_proposals(self) -> list[dict[str, Any]]:
        """
        Load up to _CLAIM_LIMIT proposals in APPROVED status.
        Returns minimal dicts: proposal_id, goal.
        """
        from body.services.service_registry import service_registry
        from will.autonomy.proposal import ProposalStatus
        from will.autonomy.proposal_repository import ProposalRepository

        try:
            async with service_registry.session() as session:
                repo = ProposalRepository(session)
                proposals = await repo.list_by_status(
                    ProposalStatus.APPROVED, limit=_CLAIM_LIMIT
                )
                return [
                    {"proposal_id": p.proposal_id, "goal": p.goal} for p in proposals
                ]
        except Exception as e:
            logger.error(
                "ProposalConsumerWorker: failed to load approved proposals: %s", e
            )
            return []
