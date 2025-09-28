# src/services/database/models.py
"""
SQLAlchemy ORM models for CORE's operational database.
"""
from __future__ import annotations

from sqlalchemy import JSON, Column, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


# ID: c852a470-27f9-4ed2-911b-073c32692420
class CliCommand(Base):
    """Maps to the core.cli_commands table."""

    __tablename__ = "cli_commands"
    # __table_args__ is removed to be compatible with both PG and SQLite
    name: str = Column(String, primary_key=True)
    module: str = Column(String, nullable=False)
    entrypoint: str = Column(String, nullable=False)
    summary: str | None = Column(Text)
    category: str | None = Column(String)


# ID: e2d390c6-dd16-472e-9de7-2f9a4b683a7e
class LlmResource(Base):
    """Maps to the core.llm_resources table."""

    __tablename__ = "llm_resources"
    name: str = Column(String, primary_key=True)
    provided_capabilities: list[str] = Column(JSON, nullable=False, default=[])
    env_prefix: str = Column(String, nullable=False, unique=True)
    performance_metadata: dict | None = Column(JSON)


# ID: a01d888a-367f-4c67-ba6a-8947f175e997
class CognitiveRole(Base):
    """Maps to the core.cognitive_roles table."""

    __tablename__ = "cognitive_roles"
    role: str = Column("role", String, primary_key=True)
    description: str | None = Column(Text)
    assigned_resource: str | None = Column(String)
    required_capabilities: list[str] = Column(JSON, nullable=False, default=[])
