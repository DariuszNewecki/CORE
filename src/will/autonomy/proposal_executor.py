# src/will/autonomy/proposal_executor.py
# ID: autonomy.proposal_executor
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

from body.atomic.executor import ActionExecutor
from body.services.service_registry import service_registry
from shared.logger import getLogger
from will.autonomy.proposal import ProposalStatus
from will.autonomy.proposal_repository import ProposalRepository


logger = getLogger(__name__)


# ID: proposal_executor
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

    # ID: executor_execute
    # ID: 5bb8175a-6a30-4548-8597-977a43fcb0b7
    async def execute(
        self,
        proposal_id: str,
        write: bool = False,
    ) -> dict[str, Any]:
        start_time = time.time()

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

            # 3. Mark as executing (only if write=True)
            if write:
                await repo.mark_executing(proposal.proposal_id)
                logger.info("Marked proposal as executing: %s", proposal.proposal_id)
            else:
                logger.info("DRY-RUN mode - not updating proposal status")

            # 4. Execute actions in order
            action_results: dict[str, Any] = {}
            all_ok = True

            sorted_actions = sorted(proposal.actions, key=lambda a: a.order)

            logger.info("Executing %d actions...", len(sorted_actions))

            for action in sorted_actions:
                action_start = time.time()
                action_id = action.action_id

                logger.info(
                    "Executing action %d/%d: %s",
                    action.order + 1,
                    len(sorted_actions),
                    action_id,
                )

                try:
                    result = await self.action_executor.execute(
                        action_id=action_id,
                        write=write,
                        **action.parameters,
                    )

                    action_duration = time.time() - action_start

                    action_results[action_id] = {
                        "ok": result.ok,
                        "duration_sec": action_duration,
                        "data": result.data,
                        "order": action.order,
                    }

                    if not result.ok:
                        all_ok = False
                        logger.warning(
                            "Action %s failed: %s",
                            action_id,
                            (result.data or {}).get("error", "Unknown error"),
                        )
                    else:
                        logger.info(
                            "Action %s completed successfully (%.2fs)",
                            action_id,
                            action_duration,
                        )

                except Exception as e:
                    action_duration = time.time() - action_start
                    all_ok = False

                    logger.error(
                        "Exception executing %s: %s",
                        action_id,
                        e,
                        exc_info=True,
                    )

                    action_results[action_id] = {
                        "ok": False,
                        "duration_sec": action_duration,
                        "data": {"error": str(e), "error_type": type(e).__name__},
                        "order": action.order,
                    }

            # 5. Update final status
            total_duration = time.time() - start_time

            if write:
                if all_ok:
                    await repo.mark_completed(
                        proposal.proposal_id,
                        results=action_results,
                    )
                    logger.info(
                        "Proposal completed successfully: %s (%.2fs)",
                        proposal.proposal_id,
                        total_duration,
                    )
                else:
                    failed_actions = [
                        aid for aid, res in action_results.items() if not res["ok"]
                    ]
                    reason = f"Actions failed: {', '.join(failed_actions)}"
                    await repo.mark_failed(proposal.proposal_id, reason=reason)
                    logger.error(
                        "Proposal failed: %s - %s", proposal.proposal_id, reason
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
                "duration_sec": total_duration,
            }

    # ID: executor_execute_batch
    # ID: 5e4800f3-ea82-483c-9ecb-1a27a43e516d
    async def execute_batch(
        self,
        proposal_ids: list[str],
        write: bool = False,
    ) -> dict[str, Any]:
        start_time = time.time()
        results: dict[str, Any] = {}

        logger.info("Executing batch of %d proposals...", len(proposal_ids))

        # Single session reused for the whole batch
        async with service_registry.session() as session:
            repo = ProposalRepository(session)

            for proposal_id in proposal_ids:
                try:
                    # Inline execute logic but reusing the same session/repo
                    single_start = time.time()

                    proposal = await repo.get(proposal_id)
                    if not proposal:
                        results[proposal_id] = {
                            "ok": False,
                            "error": f"Proposal not found: {proposal_id}",
                            "duration_sec": time.time() - single_start,
                        }
                        continue

                    if proposal.status != ProposalStatus.APPROVED:
                        results[proposal_id] = {
                            "ok": False,
                            "error": f"Proposal not approved (status={proposal.status.value})",
                            "proposal_id": proposal.proposal_id,
                            "status": proposal.status.value,
                            "duration_sec": time.time() - single_start,
                        }
                        continue

                    if write:
                        await repo.mark_executing(proposal.proposal_id)

                    action_results: dict[str, Any] = {}
                    all_ok = True
                    sorted_actions = sorted(proposal.actions, key=lambda a: a.order)

                    for action in sorted_actions:
                        action_start = time.time()
                        action_id = action.action_id

                        try:
                            r = await self.action_executor.execute(
                                action_id=action_id,
                                write=write,
                                **action.parameters,
                            )
                            action_results[action_id] = {
                                "ok": r.ok,
                                "duration_sec": time.time() - action_start,
                                "data": r.data,
                                "order": action.order,
                            }
                            if not r.ok:
                                all_ok = False
                        except Exception as e:
                            all_ok = False
                            action_results[action_id] = {
                                "ok": False,
                                "duration_sec": time.time() - action_start,
                                "data": {
                                    "error": str(e),
                                    "error_type": type(e).__name__,
                                },
                                "order": action.order,
                            }

                    if write:
                        if all_ok:
                            await repo.mark_completed(
                                proposal.proposal_id,
                                results=action_results,
                            )
                        else:
                            failed_actions = [
                                aid
                                for aid, res in action_results.items()
                                if not res["ok"]
                            ]
                            reason = f"Actions failed: {', '.join(failed_actions)}"
                            await repo.mark_failed(proposal.proposal_id, reason=reason)

                    results[proposal_id] = {
                        "ok": all_ok,
                        "proposal_id": proposal.proposal_id,
                        "goal": proposal.goal,
                        "write": write,
                        "actions_executed": len(action_results),
                        "actions_succeeded": sum(
                            1 for r in action_results.values() if r["ok"]
                        ),
                        "actions_failed": sum(
                            1 for r in action_results.values() if not r["ok"]
                        ),
                        "action_results": action_results,
                        "duration_sec": time.time() - single_start,
                    }

                except Exception as e:
                    logger.error(
                        "Batch execution failed for %s: %s",
                        proposal_id,
                        e,
                        exc_info=True,
                    )
                    results[proposal_id] = {
                        "ok": False,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }

        total_duration = time.time() - start_time
        succeeded = sum(1 for r in results.values() if r.get("ok", False))
        failed = len(results) - succeeded

        logger.info(
            "Batch execution complete: %d succeeded, %d failed (%.2fs)",
            succeeded,
            failed,
            total_duration,
        )

        return {
            "ok": failed == 0,
            "total": len(proposal_ids),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
            "duration_sec": total_duration,
        }
