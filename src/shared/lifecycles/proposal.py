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
    """Proposal lifecycle states."""

    DRAFT = "draft"
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
