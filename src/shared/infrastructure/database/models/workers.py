# src/shared/infrastructure/database/models/workers.py
# ID: model.workers
"""
Worker Registry and Blackboard models.

Two tables supporting the constitutional Worker model:
- WorkerRegistry: identity register, workers declare here on startup
- BlackboardEntry: coordination ledger, the only channel between workers
"""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as pgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .knowledge import Base


# ID: b1c2d3e4-f5a6-7890-bcde-f12345678901
class WorkerRegistry(Base):
    """
    Constitutional identity register.

    Workers declare here on startup. Proposals without a valid
    registration are rejected before reaching any gate.
    """

    __tablename__: ClassVar[str] = "worker_registry"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    worker_uuid: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), nullable=False, unique=True
    )
    worker_name: Mapped[str] = mapped_column(Text, nullable=False)
    worker_class: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # sensing | acting | governance | supervision
    phase: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # audit | runtime | execution
    declared_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_heartbeat: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="active"
    )  # active | stopped | abandoned


# ID: c2d3e4f5-a6b7-8901-cdef-234567890123
class BlackboardEntry(Base):
    """
    Constitutional coordination ledger.

    Workers read and write here. No worker communicates directly
    with another worker — the blackboard is the only channel.
    Silence from a worker is itself a constitutional signal.
    """

    __tablename__: ClassVar[str] = "blackboard_entries"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    worker_uuid: Mapped[uuid.UUID] = mapped_column(pgUUID(as_uuid=True), nullable=False)
    entry_type: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # finding | claim | proposal | report | heartbeat
    phase: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # audit | runtime | execution
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="open"
    )  # open | claimed | resolved | abandoned
    subject: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # what this entry is about
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    claimed_by: Mapped[uuid.UUID | None] = mapped_column(pgUUID(as_uuid=True))
    claimed_at: Mapped[Any] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[Any] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
