# src/shared/infrastructure/database/models.py

"""Provides functionality for the models module."""

from __future__ import annotations

from sqlalchemy import (
    JSON,
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
from sqlalchemy.orm import declarative_base


Base = declarative_base()


# =============================================================================
# SECTION 1: KNOWLEDGE LAYER
# =============================================================================


# ID: d3ba0e25-7ab1-462e-98d7-dd1139e66504
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
    key = Column(Text)
    intent = Column(Text)
    embedding_model = Column(Text, server_default="text-embedding-3-small")
    last_embedded = Column(DateTime(timezone=True))

    # --- THIS IS THE REQUIRED FIX ---
    calls = Column(JSON, server_default="[]")
    # --- END OF FIX ---

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


# ... (The rest of the file remains unchanged)
# ID: 87092c28-9124-4b1e-8445-0982a405e5c8
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


# ID: c2f3d24c-4be0-4374-bb10-9e53a1147adb
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


# ID: 7b9e72cc-e689-4f9c-ae3c-0b949e10b488
class Domain(Base):
    __tablename__ = "domains"
    __table_args__ = {"schema": "core"}
    key = Column(Text, primary_key=True)
    title = Column(Text, nullable=False)
    description = Column(Text)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ID: 96906bd9-4298-460e-93b1-5f6b742938ea
class Proposal(Base):
    __tablename__ = "proposals"
    __table_args__ = {"schema": "core"}

    id = Column(BigInteger, primary_key=True)
    target_path = Column(Text, nullable=False)
    content_sha256 = Column(Text, nullable=False)
    justification = Column(Text, nullable=False)
    risk_tier = Column(Text, server_default="low")
    is_critical = Column(Boolean, nullable=False, server_default="false")
    status = Column(Text, nullable=False, server_default="open")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by = Column(Text, nullable=False)


# ID: 38b3e437-91cf-479d-adb5-33900948936b
class ProposalSignature(Base):
    __tablename__ = "proposal_signatures"
    __table_args__ = {"schema": "core"}

    proposal_id = Column(BigInteger, ForeignKey("core.proposals.id"), primary_key=True)
    approver_identity = Column(Text, primary_key=True)
    signature_base64 = Column(Text, nullable=False)
    signed_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    is_valid = Column(Boolean, nullable=False, server_default="true")


# ID: f2781cd9-cead-4404-b37b-88525961c6a8
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


# ID: db623f71-1cb2-455c-a79d-7b3935753dff
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


# ID: 7522bfe5-f9ba-4e22-8920-f6a5332c8079
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
    failure_reason = Column(Text)
    relevant_symbols = Column(JSON)
    context_retrieval_query = Column(Text)
    context_retrieved_at = Column(DateTime(timezone=True))
    context_tokens_used = Column(Integer)
    requires_approval = Column(Boolean, server_default="false")
    proposal_id = Column(BigInteger, ForeignKey("core.proposals.id"))
    estimated_complexity = Column(Integer)
    actual_duration_seconds = Column(Integer)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))


# ID: a8009aa5-296f-438f-b7aa-ae536448dae9
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


# ID: 1404ffe4-385a-4a5b-8f39-bbcc53bcaf89
class SymbolVectorLink(Base):
    __tablename__ = "symbol_vector_links"
    __table_args__ = {"schema": "core"}
    symbol_id = Column(
        pgUUID(as_uuid=True), ForeignKey("core.symbols.id"), primary_key=True
    )
    vector_id = Column(Text, nullable=False)
    embedding_model = Column(Text, nullable=False)
    embedding_version = Column(Integer, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ID: 1b2f55c4-308d-4bfb-85b0-b4af67333158
class CliCommand(Base):
    __tablename__ = "cli_commands"
    __table_args__ = {"schema": "core"}
    name = Column(Text, primary_key=True)
    module = Column(Text, nullable=False)
    entrypoint = Column(Text, nullable=False)
    summary = Column(Text)
    category = Column(Text)


# ID: 418c27b8-92db-4b75-8095-272f39d0b42b
class RuntimeService(Base):
    __tablename__ = "runtime_services"
    __table_args__ = {"schema": "core"}
    name = Column(Text, primary_key=True)
    implementation = Column(Text, nullable=False, unique=True)
    is_active = Column(Boolean, server_default="true")


# ID: c1c39721-a753-4b2d-b479-d7625b8a8b4c
class Migration(Base):
    __tablename__ = "_migrations"
    __table_args__ = {"schema": "core"}
    id = Column(Text, primary_key=True)
    applied_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ID: 40cddff3-85c6-4aa9-8f07-c56e7359eb84
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


# ID: 102cc7b6-adc7-4020-9a5c-c0dcdbe9ea0b
class RuntimeSetting(Base):
    __tablename__ = "runtime_settings"
    __table_args__ = {"schema": "core"}
    key = Column(Text, primary_key=True)
    value = Column(Text)
    description = Column(Text)
    is_secret = Column(Boolean, nullable=False, server_default="false")
    last_updated = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
