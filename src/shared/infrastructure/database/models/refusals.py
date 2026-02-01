# src/shared/infrastructure/database/models/refusals.py
# ID: model.shared.infrastructure.database.models.refusals

"""
Refusal Registry - Constitutional Refusal Tracking

Stores all refusals (first-class outcomes) for constitutional compliance auditing.
Enables `core-admin inspect refusals` command.

Constitutional Principles:
- "Refusal as first-class outcome" - refusals are legitimate decisions, not errors
- knowledge.database_ssot: DB is source of truth for refusal history
- observability: All refusals must be traceable and auditable
- safe_by_default: Never block operations, gracefully degrade if storage fails
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import ClassVar

from sqlalchemy import DateTime, Float, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as pgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .knowledge import Base


# ID: refusal-registry-model
# ID: a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d
class RefusalRecord(Base):
    """
    Records constitutional refusals from autonomous operations.

    Each refusal record contains:
    - What was refused and why (with policy citation)
    - When and by which component
    - Refusal type (boundary, confidence, extraction, etc.)
    - Suggested action for user
    - Original request for audit trail

    Used by:
    - `core-admin inspect refusals` for constitutional compliance auditing
    - Quality improvement analysis
    - Constitutional boundary verification
    - User experience improvement
    """

    __tablename__: ClassVar[str] = "refusals"
    __table_args__: ClassVar[dict] = {"schema": "core"}

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Refusal identification
    component_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
        comment="Which component refused (code_generator, planner, etc.)",
    )

    phase: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
        comment="Component phase where refusal occurred (EXECUTION, PARSE, etc.)",
    )

    # Refusal categorization
    refusal_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
        comment="Category: boundary, confidence, contradiction, assumption, capability, extraction, quality",
    )

    # Refusal details
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Constitutional reason for refusal (with policy citation)",
    )

    suggested_action: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="What user should do to address the refusal",
    )

    original_request: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="The request that was refused (for audit trail)",
    )

    # Confidence tracking
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        server_default="0.0",
        comment="Confidence score at time of refusal (often low)",
    )

    # Additional context
    context_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Additional context (boundaries violated, metrics, etc.)",
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
        comment="When refusal occurred",
    )

    # Session tracking (optional - links to decision traces)
    session_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        index=True,
        comment="Decision trace session ID if refusal occurred during traced session",
    )

    # User tracking
    user_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        index=True,
        comment="User who received the refusal (for UX improvement analysis)",
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<RefusalRecord(id={self.id}, "
            f"type={self.refusal_type}, "
            f"component={self.component_id}, "
            f"phase={self.phase})>"
        )
