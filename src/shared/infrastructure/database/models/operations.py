# src/shared/infrastructure/database/models/operations.py
# ID: model.shared.infrastructure.database.models.operations
"""
Operations Layer models for CORE v2.2 Schema.
Section 3: Tasks, Actions, LLM Resources, Cognitive Roles - The Body.
"""

from __future__ import annotations

import uuid
from typing import ClassVar

from sqlalchemy import (
    ARRAY,
    Boolean,
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


# ID: f2781cd9-cead-4404-b37b-88525961c6a8
class LlmResource(Base):
    __tablename__: ClassVar[str] = "llm_resources"
    __table_args__: ClassVar[dict] = {"schema": "core"}
    name = Column(Text, primary_key=True)
    env_prefix = Column(Text, nullable=False, unique=True)
    provided_capabilities = Column(JSONB, server_default="[]")
    performance_metadata = Column(JSONB)
    is_available = Column(Boolean, server_default="true")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ID: db623f71-1cb2-455c-a79d-7b3935753dff
class CognitiveRole(Base):
    __tablename__: ClassVar[str] = "cognitive_roles"
    __table_args__: ClassVar[dict] = {"schema": "core"}
    role = Column(Text, primary_key=True)
    description = Column(Text)
    assigned_resource = Column(Text, ForeignKey("core.llm_resources.name"))
    required_capabilities = Column(JSONB, server_default="[]")
    max_concurrent_tasks = Column(Integer, server_default="1")
    specialization = Column(JSONB)
    is_active = Column(Boolean, server_default="true")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ID: 7522bfe5-f9ba-4e22-8920-f6a5332c8079
class Task(Base):
    __tablename__: ClassVar[str] = "tasks"
    __table_args__: ClassVar[dict] = {"schema": "core"}
    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    intent = Column(Text, nullable=False)
    assigned_role = Column(Text, ForeignKey("core.cognitive_roles.role"))
    parent_task_id = Column(pgUUID(as_uuid=True), ForeignKey("core.tasks.id"))
    status = Column(Text, nullable=False, server_default="pending")
    plan = Column(JSONB)
    context = Column(JSONB, server_default="{}")
    error_message = Column(Text)
    failure_reason = Column(Text)

    # Matches SQL: relevant_symbols uuid[]
    relevant_symbols = Column(ARRAY(pgUUID(as_uuid=True)))

    context_retrieval_query = Column(Text)
    context_retrieved_at = Column(DateTime(timezone=True))
    context_tokens_used = Column(Integer)
    requires_approval = Column(Boolean, server_default="false")
    proposal_id = Column(Integer, ForeignKey("core.proposals.id"))
    estimated_complexity = Column(Integer)
    actual_duration_seconds = Column(Integer)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))


# ID: a8009aa5-296f-438f-b7aa-ae536448dae9
class Action(Base):
    __tablename__: ClassVar[str] = "actions"
    __table_args__: ClassVar[dict] = {"schema": "core"}
    id = Column(
        pgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    task_id = Column(pgUUID(as_uuid=True), ForeignKey("core.tasks.id"), nullable=False)
    action_type = Column(Text, nullable=False)
    target = Column(Text)
    payload = Column(JSONB)
    result = Column(JSONB)
    success = Column(Boolean, nullable=False)
    cognitive_role = Column(Text, nullable=False)
    reasoning = Column(Text)
    duration_ms = Column(Integer)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
