# src/shared/infrastructure/database/models/autonomous_proposals.py
"""
A3 Autonomous Proposal System models.

Stores registry-based action plans for autonomous execution.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as pgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .knowledge import Base


# ID: c35e1baa-f0a4-479a-ab4f-d0745bb30d59
class AutonomousProposal(Base):
    """
    A3 Autonomous Proposal - Registry-based action plan.

    Stores autonomous proposals that reference actions from action_registry.
    """

    __tablename__ = "autonomous_proposals"
    __table_args__ = (
        # ADR-015 D2: approval_authority must be set once approved/executing/completed.
        # Historical NULL carve-out for proposals created before the constraint landed.
        CheckConstraint(
            "(status <> ALL (ARRAY['approved', 'executing', 'completed']))"
            " OR (approval_authority IS NOT NULL)"
            " OR (created_at < '2026-04-27 00:00:00+00')",
            name="approval_authority_required_when_approved",
        ),
        CheckConstraint(
            "(approval_authority IS NULL)"
            " OR (approval_authority = ANY (ARRAY["
            "'risk_classification.safe_auto_approval', 'principal.governor']))",
            name="autonomous_proposals_approval_authority_value_check",
        ),
        CheckConstraint(
            "status = ANY (ARRAY["
            "'draft', 'pending', 'approved', 'executing', 'completed', 'failed', 'rejected'])",
            name="autonomous_proposals_status_check",
        ),
        {"schema": "core"},
    )

    # Primary key (UUID)
    id = Column(pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Human-readable identifier
    proposal_id = Column(Text, unique=True, nullable=False, index=True)

    # Core proposal data
    goal = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default="draft", index=True)

    # Actions (JSONB array)
    # Format: [{"action_id": "fix.format", "parameters": {}, "order": 0}]
    actions = Column(JSONB, nullable=False)

    # Scope (JSONB object)
    # Format: {"files": [], "modules": [], "symbols": [], "policies": []}
    scope = Column(JSONB, nullable=False, server_default="{}")

    # Risk assessment (JSONB object)
    # Format: {"overall_risk": "safe", "action_risks": {}, "risk_factors": [], "mitigation": []}
    risk = Column(JSONB)

    # Metadata
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    created_by = Column(Text, nullable=False, server_default="autonomous", index=True)

    # Validation
    validation_checks = Column(JSONB, nullable=False, server_default="[]")
    validation_results = Column(JSONB, nullable=False, server_default="{}")

    # Execution tracking
    claimed_by = Column(pgUUID(as_uuid=True))
    execution_started_at = Column(DateTime(timezone=True))
    execution_completed_at = Column(DateTime(timezone=True))
    execution_results = Column(JSONB, nullable=False, server_default="{}")

    # Constitutional governance
    constitutional_constraints = Column(JSONB, nullable=False, server_default="{}")
    approval_required = Column(Boolean, nullable=False, server_default="false")
    approved_by = Column(Text)
    approved_at = Column(DateTime(timezone=True))
    approval_authority = Column(Text)

    # Failure tracking
    failure_reason = Column(Text)

    # Optimistic locking / audit
    version = Column(Integer, nullable=False, server_default="0")
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ID: f402eb28-e75d-416e-8e1a-074a625ca9c6
class ProposalConsequence(Base):
    """Consequence log: records what each executed proposal actually changed.

    Closes the causal chain: Finding → Proposal → Approval → Execution → File Changes.
    One row per proposal, keyed by proposal_id (FK to autonomous_proposals.proposal_id).

    Added as ADR-016 D1 prerequisite: the table existed in production but had no
    SQLAlchemy model, making it invisible to Base.metadata.create_all.
    """

    __tablename__ = "proposal_consequences"
    __table_args__ = ({"schema": "core"},)

    proposal_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("core.autonomous_proposals.proposal_id"),
        primary_key=True,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    pre_execution_sha: Mapped[str | None] = mapped_column(Text)
    post_execution_sha: Mapped[str | None] = mapped_column(Text)
    files_changed: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    findings_resolved: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    authorized_by_rules: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    declared_production: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
