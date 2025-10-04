# src/services/database/models.py
"""
SQLAlchemy ORM models for CORE's operational database.
"""
from __future__ import annotations

from sqlalchemy import JSON, Boolean, Column, Numeric, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


# --- EXISTING MODELS ---


# ID: 1fd4488a-09e0-46ea-8bca-0d61b1abff9f
class CliCommand(Base):
    """Maps to the core.cli_commands table."""

    __tablename__ = "cli_commands"
    __table_args__ = {"schema": "core"}
    name: str = Column(String, primary_key=True)
    module: str = Column(String, nullable=False)
    entrypoint: str = Column(String, nullable=False)
    summary: str | None = Column(Text)
    category: str | None = Column(String)


# ID: c4f313ac-ffb5-43a8-bf6e-b19464983a61
class LlmResource(Base):
    """Maps to the core.llm_resources table."""

    __tablename__ = "llm_resources"
    __table_args__ = {"schema": "core"}
    name: str = Column(String, primary_key=True)
    provided_capabilities: list[str] = Column(JSON, nullable=False, default=[])
    env_prefix: str = Column(String, nullable=False, unique=True)
    performance_metadata: dict | None = Column(JSON)


# ID: 03059618-ebaa-46ca-b86c-65d207bf0313
class CognitiveRole(Base):
    """Maps to the core.cognitive_roles table."""

    __tablename__ = "cognitive_roles"
    __table_args__ = {"schema": "core"}
    role: str = Column("role", String, primary_key=True)
    description: str | None = Column(Text)
    assigned_resource: str | None = Column(String)
    required_capabilities: list[str] = Column(JSON, nullable=False, default=[])


# --- NEW MODELS FOR SSOT ---


# ID: ca1987e3-9067-4f94-9ac3-085ef05a9fc9
class Capability(Base):
    __tablename__ = "capabilities"
    __table_args__ = {"schema": "core"}
    id = Column(String, primary_key=True)
    name = Column(Text, nullable=False)
    objective = Column(Text)
    owner = Column(Text)
    domain = Column(Text, nullable=False, default="general")
    tags = Column(JSON, nullable=False, default=[])
    status = Column(Text, nullable=False, default="Active")


# ID: 68b413a5-241e-476d-85e8-c2761149efd3
class Symbol(Base):
    __tablename__ = "symbols"
    __table_args__ = {"schema": "core"}
    id = Column(String, primary_key=True)
    module = Column(Text, nullable=False)
    qualname = Column(Text, nullable=False)
    kind = Column(Text, nullable=False)
    ast_signature = Column(Text, nullable=False)
    fingerprint = Column(Text, nullable=False)
    state = Column(Text, nullable=False, default="discovered")


# ID: 4a43fc1a-11db-4635-8acf-d6c793eebe97
class SymbolCapabilityLink(Base):
    __tablename__ = "symbol_capability_links"
    __table_args__ = {"schema": "core"}
    symbol_id = Column(String, primary_key=True)
    capability_id = Column(String, primary_key=True)
    source = Column(Text, primary_key=True)
    confidence = Column(Numeric, nullable=False)
    verified = Column(Boolean, nullable=False, default=False)


# ID: 1d40bfaa-63c1-4249-8331-4b1bcad8474e
class Northstar(Base):
    __tablename__ = "northstar"
    __table_args__ = {"schema": "core"}
    id = Column(String, primary_key=True)
    mission = Column(Text, nullable=False)
