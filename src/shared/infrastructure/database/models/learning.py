# src/shared/infrastructure/database/models/learning.py
# ID: model.shared.infrastructure.database.models.learning
"""
Learning & Feedback Layer models for CORE v2.2 Schema.
Section 5: Agent decisions, memory, feedback - The Will.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import ClassVar

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as pgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .knowledge import Base


# ID: 91b2d3e4-agent-decisions-aligned
# ID: 13cd8357-460b-464b-9c5e-94cfe8096249
class AgentDecision(Base):
    """
    Decisions made by agents. Matches CORE v2.2 schema.
    """

    __tablename__: ClassVar[str] = "agent_decisions"
    __table_args__: ClassVar[dict] = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("core.tasks.id"))
    decision_point: Mapped[str] = mapped_column(Text)
    options_considered: Mapped[dict] = mapped_column(JSONB)
    chosen_option: Mapped[str] = mapped_column(Text)
    reasoning: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2))
    was_correct: Mapped[bool | None] = mapped_column(Boolean)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ID: a2c3d4e5-agent-memory-aligned
# ID: ae0b3160-a30d-4ec7-bad9-fd42c6e940b9
class AgentMemory(Base):
    """
    Short-term and pattern memory for agents. Matches CORE v2.2 schema.
    """

    __tablename__: ClassVar[str] = "agent_memory"
    __table_args__: ClassVar[dict] = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cognitive_role: Mapped[str] = mapped_column(Text)
    memory_type: Mapped[str] = mapped_column(
        Text
    )  # fact, observation, decision, pattern, error
    content: Mapped[str] = mapped_column(Text)
    related_task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("core.tasks.id")
    )
    relevance_score: Mapped[float] = mapped_column(Numeric(3, 2), default=1.0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ID: feedback-model
# ID: 9a090789-0e88-48e9-935e-09c25aeaa944
class Feedback(Base):
    __tablename__: ClassVar[str] = "feedback"
    __table_args__: ClassVar[dict] = {"schema": "core"}

    id = Column(pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(pgUUID(as_uuid=True), ForeignKey("core.tasks.id"))
    action_id = Column(pgUUID(as_uuid=True), ForeignKey("core.actions.id"))
    feedback_type = Column(Text, nullable=False)
    message = Column(Text, nullable=False)
    corrective_action = Column(Text)
    applied = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
