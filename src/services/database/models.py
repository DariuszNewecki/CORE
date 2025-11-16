# src/services/database/models.py
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


# ID: 2cc67cc1-1eed-4bde-a5d0-718898c13e7d
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


# ID: 4932bee2-69e1-4849-aa68-b8f99493da6f
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


# ID: b1b4c985-b551-41f6-8f54-805c9baea7ef
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


# ID: 7f6f266f-0134-4f49-96f0-74221fffb235
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
# SECTION 2: GOVERNANCE LAYER (Constitutional compliance)
# =============================================================================


# ID: 9467fb58-3f84-472a-9f59-ef5444bcebb9
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


# ID: e8f6ca99-95a9-4097-b133-f1d9103dcc57
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


# =============================================================================
# SECTION 3: OPERATIONAL LAYER
# =============================================================================


# ID: b00a4201-294c-4fbf-8ae5-d6a5e42d7db7
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


# ID: 869fa796-6848-4e73-aa02-e9f1f16dd2b2
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


# ID: 30c36fed-1175-4352-b585-4822f68f9eb9
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


# ID: 0b4c145d-c20d-4a6e-ad90-0dd172ab9d1e
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
# SECTION 4: VECTOR INTEGRATION LAYER
# =============================================================================


# ID: 200ed659-c322-4c49-b098-0ecc877d0276
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


# =============================================================================
# SECTION 6: SYSTEM METADATA
# =============================================================================


# ID: 7cb97df4-dc18-49e3-8ef1-6dcc752efebd
class CliCommand(Base):
    __tablename__ = "cli_commands"
    __table_args__ = {"schema": "core"}
    name = Column(Text, primary_key=True)
    module = Column(Text, nullable=False)
    entrypoint = Column(Text, nullable=False)
    summary = Column(Text)
    category = Column(Text)


# ID: c9d097a0-89dd-4769-97a5-4d213720d120
class RuntimeService(Base):
    __tablename__ = "runtime_services"
    __table_args__ = {"schema": "core"}
    name = Column(Text, primary_key=True)
    implementation = Column(Text, nullable=False, unique=True)
    is_active = Column(Boolean, server_default="true")


# ID: 4b0d98d6-23a0-4c9f-8389-0d40e7ef2105
class Migration(Base):
    __tablename__ = "_migrations"
    __table_args__ = {"schema": "core"}
    id = Column(Text, primary_key=True)
    applied_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ID: 15a8b3cf-3c2d-4504-9890-85a386700323
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


# --- START OF FIX: ADD THE MISSING RUNTIMESETTING MODEL ---
# ID: f8c994c5-9af8-49ba-b7fd-76df01ad7f2a
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


# --- END OF FIX ---
