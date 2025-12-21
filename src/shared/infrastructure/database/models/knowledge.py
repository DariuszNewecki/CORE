# src/shared/infrastructure/database/models/knowledge.py
# ID: model.shared.infrastructure.database.models.knowledge
"""
Knowledge Layer models for CORE v2.2 Schema.
Section 1: Symbols, Capabilities, Domains - The Mind.
"""

from __future__ import annotations

from typing import ClassVar

from sqlalchemy import (
    ARRAY,
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
from sqlalchemy.orm import declarative_base


Base = declarative_base()


# ID: d3ba0e25-7ab1-462e-98d7-dd1139e66504
class Symbol(Base):
    __tablename__: ClassVar[str] = "symbols"
    __table_args__: ClassVar[dict] = {"schema": "core"}
    id = Column(
        pgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    symbol_path = Column(Text, nullable=False, unique=True)
    module = Column(Text, nullable=False)
    qualname = Column(Text, nullable=False)
    kind = Column(Text, nullable=False)
    domain = Column(Text, nullable=False, server_default="unknown")
    ast_signature = Column(Text, nullable=False)
    fingerprint = Column(Text, nullable=False)
    state = Column(Text, nullable=False, server_default="discovered")
    health_status = Column(Text, server_default="unknown")
    is_public = Column(Boolean, nullable=False, server_default="true")
    previous_paths = Column(ARRAY(Text))
    key = Column(Text)
    intent = Column(Text)
    embedding_model = Column(Text, server_default="text-embedding-3-small")
    last_embedded = Column(DateTime(timezone=True))

    calls = Column(JSONB, server_default="[]")

    first_seen = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_modified = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ID: 87092c28-9124-4b1e-8445-0982a405e5c8
class Capability(Base):
    __tablename__: ClassVar[str] = "capabilities"
    __table_args__: ClassVar[dict] = {"schema": "core"}
    id = Column(
        pgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name = Column(Text, nullable=False)
    domain = Column(Text, nullable=False, server_default="general")
    title = Column(Text, nullable=False)
    objective = Column(Text)
    owner = Column(Text, nullable=False)
    dependencies = Column(JSONB, server_default="[]")
    test_coverage = Column(Numeric(5, 2))
    tags = Column(JSONB, nullable=False, server_default="[]")
    status = Column(Text, server_default="Active")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ID: c2f3d24c-4be0-4374-bb10-9e53a1147adb
class SymbolCapabilityLink(Base):
    __tablename__: ClassVar[str] = "symbol_capability_links"
    __table_args__: ClassVar[dict] = {"schema": "core"}
    symbol_id = Column(
        pgUUID(as_uuid=True), ForeignKey("core.symbols.id"), primary_key=True
    )
    capability_id = Column(
        pgUUID(as_uuid=True), ForeignKey("core.capabilities.id"), primary_key=True
    )
    source = Column(Text, primary_key=True)
    confidence = Column(Numeric, nullable=False)
    verified = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ID: 7b9e72cc-e689-4f9c-ae3c-0b949e10b488
class Domain(Base):
    __tablename__: ClassVar[str] = "domains"
    __table_args__: ClassVar[dict] = {"schema": "core"}
    key = Column(Text, primary_key=True)
    title = Column(Text, nullable=False)
    description = Column(Text)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
