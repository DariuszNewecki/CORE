# src/shared/infrastructure/database/models/autonomous_proposals.py
# ID: model.autonomous_proposals
"""
A3 Autonomous Proposal System models.

Separate from core.proposals (which handles constitutional file replacements).
This table stores registry-based action plans for autonomous execution.
"""

from __future__ import annotations

import uuid
from typing import ClassVar

from sqlalchemy import Boolean, Column, DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as pgUUID

from .knowledge import Base


# ID: autonomous_proposal_model
# ID: c35e1baa-f0a4-479a-ab4f-d0745bb30d59
class AutonomousProposal(Base):
    """
    A3 Autonomous Proposal - Registry-based action plan.

    Stores autonomous proposals that reference actions from action_registry.
    Completely separate from the old core.proposals table which handles
    constitutional file replacement proposals with cryptographic signatures.
    """

    __tablename__: ClassVar[str] = "autonomous_proposals"
    __table_args__: ClassVar[dict] = {"schema": "core"}

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
    execution_started_at = Column(DateTime(timezone=True))
    execution_completed_at = Column(DateTime(timezone=True))
    execution_results = Column(JSONB, nullable=False, server_default="{}")

    # Constitutional governance
    constitutional_constraints = Column(JSONB, nullable=False, server_default="{}")
    approval_required = Column(Boolean, nullable=False, server_default="false")
    approved_by = Column(Text)
    approved_at = Column(DateTime(timezone=True))

    # Failure tracking
    failure_reason = Column(Text)
