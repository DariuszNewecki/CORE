# src/shared/infrastructure/database/models/system.py

"""Provides functionality for the system module."""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as pgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .knowledge import Base


# ID: a76dcc29-f703-46f2-9b52-66e7261b1e3e
class CliCommand(Base):
    __tablename__: ClassVar[str] = "cli_commands"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    module: Mapped[str] = mapped_column(Text, nullable=False)
    entrypoint: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)


# ID: 40854a23-67ce-4cbd-80f4-800152ae98fe
class RuntimeService(Base):
    __tablename__: ClassVar[str] = "runtime_services"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    implementation: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")


# ID: 952d44ef-52a3-4101-8aad-610bea45c175
class Migration(Base):
    __tablename__: ClassVar[str] = "_migrations"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    applied_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ID: 95b1800b-7286-4608-b2e4-49d77be98d2a
class ContextPacket(Base):
    __tablename__: ClassVar[str] = "context_packets"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    packet_id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[str] = mapped_column(String(255))
    task_type: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[Any] = mapped_column(
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
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default={})
    builder_version: Mapped[str] = mapped_column(String(20))


# ID: 06535678-f663-4668-af56-97f86c12e7ee
class Northstar(Base):
    __tablename__: ClassVar[str] = "northstar"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    mission: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ID: b96ce43c-edf8-4f70-bc20-1541e9ee281a
class RuntimeSetting(Base):
    __tablename__: ClassVar[str] = "runtime_settings"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    is_secret: Mapped[bool] = mapped_column(Boolean, server_default="false")
    last_updated: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
