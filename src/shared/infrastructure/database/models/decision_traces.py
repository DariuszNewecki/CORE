# src/shared/infrastructure/database/models/decision_traces.py
# ID: 2d9f9691-458f-47a2-89e3-293d2ddd7aad
"""
Decision Trace Storage - Observability for Autonomous Operations

Stores complete decision traces from DecisionTracer for analysis and debugging.
Enables `core-admin inspect decisions` command.

Constitutional Principles:
- knowledge.database_ssot: DB is source of truth for decision history
- observability: All autonomous decisions must be traceable
- safe_by_default: Never block operations, gracefully degrade if storage fails
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import ClassVar

from sqlalchemy import DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as pgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .knowledge import Base


# ID: 3f7bb115-2a52-40bf-8d83-cbc594eac6f6
# ID: 69886549-e3ff-48f0-81ac-0ac88c105bb9
class DecisionTrace(Base):
    """
    Records decision traces from autonomous operations.

    Each trace contains:
    - Session metadata (when, what agent, what goal)
    - Array of individual decisions made during session
    - Pattern classifications used
    - Success/failure outcomes

    Used by:
    - `core-admin inspect decisions` for debugging
    - Pattern learning systems
    - Success rate tracking
    - Autonomous improvement analysis
    """

    __tablename__: ClassVar[str] = "decision_traces"
    __table_args__: ClassVar[dict] = {"schema": "core"}

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Session identification
    session_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
        comment="Unique session identifier from DecisionTracer",
    )

    # Agent context
    agent_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
        comment="Which agent made these decisions (CodeGenerator, Planner, etc.)",
    )

    # Task context
    goal: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="High-level goal for this session"
    )

    # Decision data (JSONB array)
    # Format: [{"agent": "...", "decision_type": "...", "rationale": "...", ...}]
    decisions: Mapped[dict] = mapped_column(
        JSONB, nullable=False, comment="Array of all decisions made in this session"
    )

    # Decision count for quick filtering
    decision_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True,
        comment="Number of decisions in this trace",
    )

    # Pattern classification (JSONB object)
    # Format: {"action_pattern": 5, "inspect_pattern": 2, ...}
    pattern_stats: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="Frequency of pattern classifications used"
    )

    # Outcome tracking
    has_violations: Mapped[bool | None] = mapped_column(
        Text,  # Using Text instead of Boolean for consistency with existing schema
        nullable=True,
        index=True,
        comment="Whether any decisions led to violations (true/false/unknown)",
    )

    violation_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Number of violations detected in this session"
    )

    # Performance metadata
    duration_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Total session duration in milliseconds"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
        comment="When this trace was created",
    )

    # Additional metadata (JSONB) ← FIXED NAME
    # Format: {"target_file": "...", "pattern_id": "...", "success_rate": 0.85, ...}
    extra_metadata: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="Additional context-specific metadata"
    )

    def __repr__(self) -> str:
        return f"<DecisionTrace {self.session_id[:8]} {self.agent_name} {self.decision_count} decisions>"
