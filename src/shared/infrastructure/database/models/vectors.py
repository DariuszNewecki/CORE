# src/shared/infrastructure/database/models/vectors.py
# ID: model.shared.infrastructure.database.models.vectors
"""
Vector Integration Layer models for CORE v2.2 Schema.
Section 4: Vector sync, semantic cache, retrieval feedback.
"""

from __future__ import annotations

import uuid
from typing import ClassVar

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as pgUUID

from .knowledge import Base


# ID: 1404ffe4-385a-4a5b-8f39-bbcc53bcaf89
class SymbolVectorLink(Base):
    __tablename__: ClassVar[str] = "symbol_vector_links"
    __table_args__: ClassVar[dict] = {"schema": "core"}
    symbol_id = Column(
        pgUUID(as_uuid=True), ForeignKey("core.symbols.id"), primary_key=True
    )
    vector_id = Column(Text, nullable=False)
    embedding_model = Column(Text, nullable=False)
    embedding_version = Column(Integer, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ID: vector-sync-log-model
# ID: 462a9d2d-a0b6-494c-a22d-6a35bbd0eb95
class VectorSyncLog(Base):
    __tablename__: ClassVar[str] = "vector_sync_log"
    __table_args__: ClassVar[dict] = {"schema": "core"}

    id = Column(BigInteger, primary_key=True)
    operation = Column(Text, nullable=False)
    symbol_ids = Column(ARRAY(pgUUID(as_uuid=True)))
    qdrant_collection = Column(Text, nullable=False)
    success = Column(Boolean, nullable=False)
    error_message = Column(Text)
    batch_size = Column(Integer)
    duration_ms = Column(Integer)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())


# ID: retrieval-feedback-model
# ID: fb375a67-e917-42c8-b9f9-42a8805a103b
class RetrievalFeedback(Base):
    __tablename__: ClassVar[str] = "retrieval_feedback"
    __table_args__: ClassVar[dict] = {"schema": "core"}

    id = Column(pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(pgUUID(as_uuid=True), ForeignKey("core.tasks.id"), nullable=False)
    query = Column(Text, nullable=False)
    retrieved_symbols = Column(ARRAY(pgUUID(as_uuid=True)))
    actually_used_symbols = Column(ARRAY(pgUUID(as_uuid=True)))
    retrieval_quality = Column(Integer)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ID: semantic-cache-model
# ID: 4cc4b693-38cc-4dfe-8ca3-ccf921b8300b
class SemanticCache(Base):
    __tablename__: ClassVar[str] = "semantic_cache"
    __table_args__: ClassVar[dict] = {"schema": "core"}

    id = Column(pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_hash = Column(Text, nullable=False, unique=True)
    query_text = Column(Text, nullable=False)
    vector_id = Column(Text)
    response_text = Column(Text, nullable=False)
    cognitive_role = Column(Text)
    llm_model = Column(Text, nullable=False)
    tokens_used = Column(Integer)
    confidence = Column(Numeric(3, 2))
    hit_count = Column(Integer, default=0)
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
