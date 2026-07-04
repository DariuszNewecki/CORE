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
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
