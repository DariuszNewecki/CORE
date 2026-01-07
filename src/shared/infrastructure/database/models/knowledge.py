# src/shared/infrastructure/database/models/knowledge.py

"""Provides functionality for the knowledge module."""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as pgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ID: 01bae779-fca9-4adb-8369-b7b5c1e35216
class Base(DeclarativeBase):
    """Declarative Base for SQLAlchemy 2.0 and MyPy."""

    type_annotation_map: ClassVar[dict[Any, Any]] = {
        dict[str, Any]: JSONB,
    }


# ID: 3fa9cd6c-3533-4dbe-bcfe-73bf554d35d1
class Domain(Base):
    __tablename__: ClassVar[str] = "domains"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ID: 838164ab-6840-4344-b5cf-00ca0436f9a5
class Symbol(Base):
    __tablename__: ClassVar[str] = "symbols"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    symbol_path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    module: Mapped[str] = mapped_column(Text, nullable=False)
    qualname: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(
        Text, ForeignKey("core.domains.key"), server_default="unknown"
    )
    ast_signature: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="discovered"
    )
    health_status: Mapped[str | None] = mapped_column(Text, server_default="unknown")
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    previous_paths: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    key: Mapped[str | None] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(Text)
    embedding_model: Mapped[str | None] = mapped_column(
        Text, server_default="text-embedding-3-small"
    )
    last_embedded: Mapped[Any | None] = mapped_column(DateTime(timezone=True))
    calls: Mapped[list[str] | None] = mapped_column(JSONB, server_default="[]")

    # Metadata Refinement fields from SQL Dump
    definition_status: Mapped[str] = mapped_column(Text, server_default="pending")
    definition_error: Mapped[str | None] = mapped_column(Text)
    definition_source: Mapped[str | None] = mapped_column(Text)
    defined_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, server_default="0")
    symbol_tier: Mapped[str | None] = mapped_column(Text, name="symbol_tier")
    file_path: Mapped[str | None] = mapped_column(Text)
    module_path: Mapped[str | None] = mapped_column(Text)

    first_seen: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_modified: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ID: bea0131b-5084-4754-91d1-a78c00bf8850
class Capability(Base):
    __tablename__: ClassVar[str] = "capabilities"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(
        Text, ForeignKey("core.domains.key"), server_default="general"
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    objective: Mapped[str | None] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(Text, nullable=False)
    dependencies: Mapped[list[str] | None] = mapped_column(JSONB, server_default="[]")
    test_coverage: Mapped[float | None] = mapped_column(Numeric(5, 2))
    tags: Mapped[list[str]] = mapped_column(JSONB, server_default="[]")
    status: Mapped[str | None] = mapped_column(Text, server_default="Active")
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ID: 19900250-a4bf-4e4b-8b0b-6bf657f75c11
class SymbolCapabilityLink(Base):
    __tablename__: ClassVar[str] = "symbol_capability_links"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    symbol_id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), ForeignKey("core.symbols.id"), primary_key=True
    )
    capability_id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), ForeignKey("core.capabilities.id"), primary_key=True
    )
    source: Mapped[str] = mapped_column(Text, primary_key=True)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ID: 763efb36-9dc1-43a4-ae58-e1bc6b22e130
class DecoratorRegistry(Base):
    __tablename__: ClassVar[str] = "decorator_registry"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    decorator_name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    full_syntax: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    framework: Mapped[str | None] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    required_for: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    parameters: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB, server_default="[]"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ID: 493aa306-d858-4dfa-8f0d-03d0755dfb28
class SymbolDecorator(Base):
    __tablename__: ClassVar[str] = "symbol_decorators"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    symbol_id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), ForeignKey("core.symbols.id"), nullable=False
    )
    decorator_id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), ForeignKey("core.decorator_registry.id"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    parameters: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, server_default="{}"
    )
    source: Mapped[str] = mapped_column(Text, server_default="inferred")
    reasoning: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
