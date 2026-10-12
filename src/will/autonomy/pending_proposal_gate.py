# src/will/autonomy/pending_proposal_gate.py
"""
Pending-proposal gate: nothing rots in front of the governor (2026-10-12).

A proposal that needs the governor is screened before it is shown:

- **Pre-approval run.** It is executed once as a dry run (ProposalExecutor,
  write=False: every action runs, nothing is written). A proposal that runs
  cleanly is marked ``validation_results["pre_approval_run"] = True`` and only
  then is it listed for approval and approvable. One that fails is rejected
  with the reason, which revives its findings so the loop tries again.
- **Expiry.** A pending proposal older than ``MAX_PENDING_AGE`` is rejected as
  expired. Rejection revives its findings (ADR-010 §7a), so the audit sensor
  re-adjudicates them against current code and the loop regenerates a fresh
  proposal if the problem still exists.

Evidence (read-only diagnosis, 2026-10-12): of 270 proposals that waited for a
human, 140 were rejected stale or broken and 51 of the 115 approved ones
failed when run.

LAYER: will/autonomy — called by ProposalConsumerWorker each cycle; writes go
through ProposalService / ProposalStateManager.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from shared.logger import getLogger


logger = getLogger(__name__)

MAX_PENDING_AGE = timedelta(hours=72)
PRE_APPROVAL_CHECK = "pre_approval_run"
_SCREEN_LIMIT = 20


@dataclass
# ID: bc4b877b-88ac-4ed6-89c3-46a820bffd70
class ScreenOutcome:
    """What one screening pass did."""

    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    expired: list[str] = field(default_factory=list)

    # ID: a4e44d01-6ee0-4590-9e9f-9fa69d809669
    def as_payload(self) -> dict[str, Any]:
        """Counts and ids for the worker's blackboard report."""
        return {
            "pre_approval_passed": self.passed,
            "pre_approval_failed": self.failed,
            "expired": self.expired,
        }


# ID: b34815c7-c7d4-45d8-bce3-d14114adea24
async def screen_pending_proposals(
    core_context: Any, claimed_by: UUID, *, now: datetime | None = None
) -> ScreenOutcome:
    """Expire old pending proposals and dry-run the unscreened ones."""
    from body.services.service_registry import service_registry
    from will.autonomy.proposal import ProposalStatus
    from will.autonomy.proposal_executor import ProposalExecutor
    from will.autonomy.proposal_repository import ProposalRepository
    from will.autonomy.proposal_service import ProposalService

    now = now or datetime.now(UTC)
    outcome = ScreenOutcome()
    async with service_registry.session() as session:
        pending = await ProposalRepository(session).list_by_status(
            ProposalStatus.PENDING
        )
    for proposal in pending:
        if not proposal.approval_required:
            continue
        pid = proposal.proposal_id
        if now - proposal.created_at > MAX_PENDING_AGE:
            async with service_registry.session() as session:
                await ProposalService(session).reject(
                    pid,
                    "Expired: pending more than 72h. Its findings are revived so "
                    "the loop regenerates it against current code.",
                )
                await session.commit()
            outcome.expired.append(pid)
            continue
        if (proposal.validation_results or {}).get(PRE_APPROVAL_CHECK) is True:
            continue
        if len(outcome.passed) + len(outcome.failed) >= _SCREEN_LIMIT:
            continue
        result = await ProposalExecutor(core_context).execute(
            pid, claimed_by, write=False
        )
        async with service_registry.session() as session:
            if result.get("ok"):
                results = dict(proposal.validation_results or {})
                results[PRE_APPROVAL_CHECK] = True
                await ProposalRepository(session).update_fields(
                    pid, {"validation_results": results}
                )
                await session.commit()
                outcome.passed.append(pid)
            else:
                reason = str(result.get("error") or "unknown error")[:300]
                await ProposalService(session).reject(
                    pid, f"Failed its pre-approval run: {reason}"
                )
                await session.commit()
                outcome.failed.append(pid)
    if outcome.passed or outcome.failed or outcome.expired:
        logger.info(
            "Pending gate: %d passed, %d failed, %d expired",
            len(outcome.passed),
            len(outcome.failed),
            len(outcome.expired),
        )
    return outcome
