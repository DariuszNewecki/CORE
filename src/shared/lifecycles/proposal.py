# src/shared/lifecycles/proposal.py
"""Proposal lifecycle state enumeration (ADR-062 canonical location).

Moved from will.autonomy.proposal to shared.lifecycles so Body-layer
components can reference it without crossing the no_body_to_will boundary.
will.autonomy.proposal re-exports this for backward compatibility.
"""

from __future__ import annotations

from enum import Enum


# ID: 86a456a9-13eb-415f-96e3-7a8622556dfe
class ProposalStatus(str, Enum):
    """Proposal lifecycle states.

    PENDING is the only pre-approval state: it is what the approval queue
    (``GET /v1/proposals`` → ``ProposalService.list_pending_approval``) lists
    and what ``ProposalStateManager.approve()`` / ``reject()`` act on.
    """

    # #885 — DRAFT ("draft") was intentionally removed. It had no governed
    # semantic function: nothing ever transitioned DRAFT → PENDING, the
    # approval queue listed only PENDING, yet approve()/reject() accepted
    # DRAFT directly — so a Proposal could be actionable by id while being
    # structurally undiscoverable through the review surface. Even the lane
    # with the most at stake (safe auto-approval) never sat in it: creation
    # went straight to APPROVED inside one transaction. Every creation site
    # now starts in PENDING. Do not reintroduce a pre-review holding state
    # under this or any other name without a governed, enforced transition
    # out of it — see the Governor's resolution recorded on #885.
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    # ADR-148: post-commit, evidence-recording state. The proposal's changes are
    # committed to git and its consequence chain is being recorded; it becomes
    # COMPLETED only once that record is durable. A stuck FINALIZING proposal is
    # recovered by rolling forward (re-driving the idempotent evidence steps),
    # never by rollback, which would double-apply the committed change.
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
