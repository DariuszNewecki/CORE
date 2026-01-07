# src/shared/infrastructure/database/models/operations.py

"""Provides functionality for the operations module."""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as pgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .knowledge import Base


# ID: 56c3df7b-4e83-4e55-8823-a8439c6beb77
class LlmResource(Base):
    __tablename__: ClassVar[str] = "llm_resources"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    env_prefix: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    provided_capabilities: Mapped[list[str]] = mapped_column(JSONB, server_default="[]")
    performance_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    is_available: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ID: 27c701a5-a757-446e-8104-ccfd9b61f068
class CognitiveRole(Base):
    __tablename__: ClassVar[str] = "cognitive_roles"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    role: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str | None] = mapped_column(Text)
    assigned_resource: Mapped[str | None] = mapped_column(
        Text, ForeignKey("core.llm_resources.name")
    )
    required_capabilities: Mapped[list[str]] = mapped_column(JSONB, server_default="[]")
    max_concurrent_tasks: Mapped[int] = mapped_column(Integer, server_default="1")
    specialization: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ID: d146d539-6a23-4850-a7e7-f38ba45e7ca6
class Task(Base):
    __tablename__: ClassVar[str] = "tasks"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    intent: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_role: Mapped[str | None] = mapped_column(
        Text, ForeignKey("core.cognitive_roles.role")
    )
    parent_task_id: Mapped[uuid.UUID | None] = mapped_column(
        pgUUID(as_uuid=True), ForeignKey("core.tasks.id")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    plan: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    error_message: Mapped[str | None] = mapped_column(Text)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    relevant_symbols: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(pgUUID(as_uuid=True))
    )

    context_retrieval_query: Mapped[str | None] = mapped_column(Text)
    context_retrieved_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True))
    context_tokens_used: Mapped[int | None] = mapped_column(Integer)
    requires_approval: Mapped[bool] = mapped_column(Boolean, server_default="false")
    proposal_id: Mapped[int | None] = mapped_column(Integer)
    estimated_complexity: Mapped[int | None] = mapped_column(Integer)
    actual_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True))


# ID: 56a8723f-0d27-4755-b9e2-bab08e355a1a
class Action(Base):
    __tablename__: ClassVar[str] = "actions"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), ForeignKey("core.tasks.id"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cognitive_role: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
