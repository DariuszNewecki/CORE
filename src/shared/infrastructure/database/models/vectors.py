# src/shared/infrastructure/database/models/vectors.py

"""Provides functionality for the vectors module."""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as pgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .knowledge import Base


# ID: 37950ce0-869d-44df-9bb7-ec42a7c5f0c5
class SymbolVectorLink(Base):
    __tablename__: ClassVar[str] = "symbol_vector_links"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    symbol_id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), ForeignKey("core.symbols.id"), primary_key=True
    )
    vector_id: Mapped[uuid.UUID] = mapped_column(pgUUID(as_uuid=True), nullable=False)
    embedding_model: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ID: db0cf699-4737-4741-8f83-69751719c2af
class VectorSyncLog(Base):
    __tablename__: ClassVar[str] = "vector_sync_log"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    symbol_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(pgUUID(as_uuid=True))
    )
    qdrant_collection: Mapped[str] = mapped_column(Text, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    batch_size: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    synced_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ID: f89cf0e2-0af1-43de-b7eb-cfe5157d5522
class RetrievalFeedback(Base):
    __tablename__: ClassVar[str] = "retrieval_feedback"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), ForeignKey("core.tasks.id"), nullable=False
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_symbols: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(pgUUID(as_uuid=True))
    )
    actually_used_symbols: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(pgUUID(as_uuid=True))
    )
    retrieval_quality: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ID: 69b4fd97-75a7-478d-9d93-76dddca186c9
class SemanticCache(Base):
    __tablename__: ClassVar[str] = "semantic_cache"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    query_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    vector_id: Mapped[str | None] = mapped_column(Text)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    cognitive_role: Mapped[str | None] = mapped_column(Text)
    llm_model: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
