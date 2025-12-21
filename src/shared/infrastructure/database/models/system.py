# src/shared/infrastructure/database/models/system.py
# ID: model.shared.infrastructure.database.models.system
"""
System Metadata & Artifacts models for CORE v2.2 Schema.
Section 6: CLI, Services, Migrations, Context Packets, Northstar, Settings.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import ClassVar

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as pgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .knowledge import Base


# ID: 1b2f55c4-308d-4bfb-85b0-b4af67333158
class CliCommand(Base):
    __tablename__: ClassVar[str] = "cli_commands"
    __table_args__: ClassVar[dict] = {"schema": "core"}
    name = Column(Text, primary_key=True)
    module = Column(Text, nullable=False)
    entrypoint = Column(Text, nullable=False)
    summary = Column(Text)
    category = Column(Text)


# ID: 418c27b8-92db-4b75-8095-272f39d0b42b
class RuntimeService(Base):
    __tablename__: ClassVar[str] = "runtime_services"
    __table_args__: ClassVar[dict] = {"schema": "core"}
    name = Column(Text, primary_key=True)
    implementation = Column(Text, nullable=False, unique=True)
    is_active = Column(Boolean, server_default="true")


# ID: c1c39721-a753-4b2d-b479-d7625b8a8b4c
class Migration(Base):
    __tablename__: ClassVar[str] = "_migrations"
    __table_args__: ClassVar[dict] = {"schema": "core"}
    id = Column(Text, primary_key=True)
    applied_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ID: context-packet-model
# ID: a033727b-4ef6-4cf0-88ce-7db88c1a127e
class ContextPacket(Base):
    """
    Metadata for ContextPackage artifacts. Matches CORE v2.2 schema Section 6A.
    """

    __tablename__: ClassVar[str] = "context_packets"
    __table_args__: ClassVar[dict] = {"schema": "core"}

    packet_id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[str] = mapped_column(String(255))
    task_type: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    privacy: Mapped[str] = mapped_column(String(20))
    remote_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    packet_hash: Mapped[str] = mapped_column(String(64))
    cache_key: Mapped[str | None] = mapped_column(String(64))

    tokens_est: Mapped[int] = mapped_column(Integer, default=0)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    build_ms: Mapped[int] = mapped_column(Integer, default=0)
    items_count: Mapped[int] = mapped_column(Integer, default=0)
    redactions_count: Mapped[int] = mapped_column(Integer, default=0)

    path: Mapped[str] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default={})
    builder_version: Mapped[str] = mapped_column(String(20))


# ID: 40cddff3-85c6-4aa9-8f07-c56e7359eb84
class Northstar(Base):
    __tablename__: ClassVar[str] = "northstar"
    __table_args__: ClassVar[dict] = {"schema": "core"}
    id = Column(
        pgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    mission = Column(Text, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ID: 102cc7b6-adc7-4020-9a5c-c0dcdbe9ea0b
class RuntimeSetting(Base):
    __tablename__: ClassVar[str] = "runtime_settings"
    __table_args__: ClassVar[dict] = {"schema": "core"}
    key = Column(Text, primary_key=True)
    value = Column(Text)
    description = Column(Text)
    is_secret = Column(Boolean, nullable=False, server_default="false")
    last_updated = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
