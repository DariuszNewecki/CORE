# src/services/database/models.py
"""
SQLAlchemy ORM models for CORE's v2.1 operational database schema.
This file is the Python representation of the database's structure and is
aligned with the v2.1 SQL schema.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
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
from sqlalchemy.orm import declarative_base

Base = declarative_base()


# =============================================================================
# SECTION 1: KNOWLEDGE LAYER
# =============================================================================


class Symbol(Base):
    __tablename__ = "symbols"
    __table_args__ = {"schema": "core"}
    id = Column(
        pgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    symbol_path = Column(Text, nullable=False, unique=True)
    module = Column(Text, nullable=False)
    qualname = Column(Text, nullable=False)
    kind = Column(Text, nullable=False)
    ast_signature = Column(Text, nullable=False)
    fingerprint = Column(Text, nullable=False)
    state = Column(Text, nullable=False, server_default="discovered")
    health_status = Column(Text, server_default="unknown")
    is_public = Column(Boolean, nullable=False, server_default="true")
    previous_paths = Column(JSON)  # Using JSON for text[]
    vector_id = Column(Text)
    embedding_model = Column(Text, server_default="text-embedding-3-small")
    embedding_version = Column(Integer, server_default="1")
    last_embedded = Column(DateTime(timezone=True))
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


class Capability(Base):
    __tablename__ = "capabilities"
    __table_args__ = {"schema": "core"}
    id = Column(
        pgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name = Column(Text, nullable=False)
    domain = Column(Text, nullable=False, server_default="general")
    title = Column(Text, nullable=False)
    objective = Column(Text)
    owner = Column(Text, nullable=False)
    entry_points = Column(JSON, server_default="[]")
    dependencies = Column(JSON, server_default="[]")
    test_coverage = Column(Numeric(5, 2))
    tags = Column(JSON, nullable=False, server_default="[]")
    status = Column(Text, server_default="Active")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SymbolCapabilityLink(Base):
    __tablename__ = "symbol_capability_links"
    __table_args__ = {"schema": "core"}
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


class Domain(Base):
    __tablename__ = "domains"
    __table_args__ = {"schema": "core"}
    key = Column(Text, primary_key=True)
    title = Column(Text, nullable=False)
    description = Column(Text)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# =============================================================================
# SECTION 2: OPERATIONAL LAYER
# =============================================================================


class LlmResource(Base):
    __tablename__ = "llm_resources"
    __table_args__ = {"schema": "core"}
    name = Column(Text, primary_key=True)
    env_prefix = Column(Text, nullable=False, unique=True)
    provided_capabilities = Column(JSON, server_default="[]")
    performance_metadata = Column(JSON)
    is_available = Column(Boolean, server_default="true")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CognitiveRole(Base):
    __tablename__ = "cognitive_roles"
    __table_args__ = {"schema": "core"}
    role = Column(Text, primary_key=True)
    description = Column(Text)
    assigned_resource = Column(Text, ForeignKey("core.llm_resources.name"))
    required_capabilities = Column(JSON, server_default="[]")
    max_concurrent_tasks = Column(Integer, server_default="1")
    specialization = Column(JSON)
    is_active = Column(Boolean, server_default="true")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = {"schema": "core"}
    id = Column(
        pgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    intent = Column(Text, nullable=False)
    assigned_role = Column(Text, ForeignKey("core.cognitive_roles.role"))
    parent_task_id = Column(pgUUID(as_uuid=True), ForeignKey("core.tasks.id"))
    status = Column(Text, nullable=False, server_default="pending")
    plan = Column(JSON)
    context = Column(JSON, server_default="{}")
    error_message = Column(Text)
    relevant_symbols = Column(JSON)
    context_retrieval_query = Column(Text)
    context_retrieved_at = Column(DateTime(timezone=True))
    context_tokens_used = Column(Integer)
    requires_approval = Column(Boolean, server_default="false")
    proposal_id = Column(Integer, ForeignKey("core.proposals.id"))
    estimated_complexity = Column(Integer)
    actual_duration_seconds = Column(Integer)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))


class Action(Base):
    __tablename__ = "actions"
    __table_args__ = {"schema": "core"}
    id = Column(
        pgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    task_id = Column(pgUUID(as_uuid=True), ForeignKey("core.tasks.id"), nullable=False)
    action_type = Column(Text, nullable=False)
    target = Column(Text)
    payload = Column(JSON)
    result = Column(JSON)
    success = Column(Boolean, nullable=False)
    cognitive_role = Column(Text, nullable=False)
    reasoning = Column(Text)
    duration_ms = Column(Integer)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# =============================================================================
# SECTION 6: SYSTEM METADATA (FIX: Added missing models)
# =============================================================================


class CliCommand(Base):
    __tablename__ = "cli_commands"
    __table_args__ = {"schema": "core"}
    name = Column(Text, primary_key=True)
    module = Column(Text, nullable=False)
    entrypoint = Column(Text, nullable=False)
    summary = Column(Text)
    category = Column(Text)


class RuntimeService(Base):
    __tablename__ = "runtime_services"
    __table_args__ = {"schema": "core"}
    name = Column(Text, primary_key=True)
    implementation = Column(Text, nullable=False, unique=True)
    is_active = Column(Boolean, server_default="true")


class Migration(Base):
    __tablename__ = "_migrations"
    __table_args__ = {"schema": "core"}
    id = Column(Text, primary_key=True)
    applied_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Northstar(Base):
    __tablename__ = "northstar"
    __table_args__ = {"schema": "core"}
    id = Column(
        pgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    mission = Column(Text, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
