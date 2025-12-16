# src/shared/infrastructure/database/models.py
# ID: model.shared.infrastructure.database.models
"""
SQLAlchemy models for CORE v2.2 Schema.
Strictly aligned with the 'Self-Improving System Schema'.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as pgUUID
from sqlalchemy.orm import Mapped, declarative_base, mapped_column


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


# =============================================================================
# SECTION 2: GOVERNANCE LAYER
# =============================================================================


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


# ID: 894a73e1-audit-run-model
# ID: ea32fc95-90ef-4735-86c0-f09ebc280a5f
class AuditRun(Base):
    __tablename__ = "audit_runs"
    __table_args__ = {"schema": "core"}

    id = Column(BigInteger, primary_key=True)
    source = Column(Text, nullable=False)
    commit_sha = Column(String(40))
    score = Column(Numeric(4, 3))
    passed = Column(Boolean, nullable=False)
    violations_found = Column(Integer, default=0)
    started_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at = Column(DateTime(timezone=True))


# =============================================================================
# SECTION 3: OPERATIONAL LAYER
# =============================================================================


# ID: f2781cd9-cead-4404-b37b-88525961c6a8
class LlmResource(Base):
    __tablename__ = "llm_resources"
    __table_args__ = {"schema": "core"}
    name = Column(Text, primary_key=True)
    env_prefix = Column(Text, nullable=False, unique=True)
    provided_capabilities = Column(JSONB, server_default="[]")
    performance_metadata = Column(JSONB)
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
    required_capabilities = Column(JSONB, server_default="[]")
    max_concurrent_tasks = Column(Integer, server_default="1")
    specialization = Column(JSONB)
    is_active = Column(Boolean, server_default="true")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ID: 7522bfe5-f9ba-4e22-8920-f6a5332c8079
class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = {"schema": "core"}
    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    intent = Column(Text, nullable=False)
    assigned_role = Column(Text, ForeignKey("core.cognitive_roles.role"))
    parent_task_id = Column(pgUUID(as_uuid=True), ForeignKey("core.tasks.id"))
    status = Column(Text, nullable=False, server_default="pending")
    plan = Column(JSONB)
    context = Column(JSONB, server_default="{}")
    error_message = Column(Text)
    failure_reason = Column(Text)

    # Matches SQL: relevant_symbols uuid[]
    relevant_symbols = Column(ARRAY(pgUUID(as_uuid=True)))

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
    payload = Column(JSONB)
    result = Column(JSONB)
    success = Column(Boolean, nullable=False)
    cognitive_role = Column(Text, nullable=False)
    reasoning = Column(Text)
    duration_ms = Column(Integer)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ID: 33b1-constitutional-violations
# ID: c1c88088-6e9e-4400-907b-578e380c8113
class ConstitutionalViolation(Base):
    __tablename__ = "constitutional_violations"
    __table_args__ = {"schema": "core"}

    id = Column(pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_id = Column(Text, nullable=False)
    symbol_id = Column(pgUUID(as_uuid=True), ForeignKey("core.symbols.id"))
    task_id = Column(pgUUID(as_uuid=True), ForeignKey("core.tasks.id"))
    severity = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    detected_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at = Column(DateTime(timezone=True))
    resolution_notes = Column(Text)


# ID: 91b2d3e4-agent-decisions-aligned
# ID: 13cd8357-460b-464b-9c5e-94cfe8096249
class AgentDecision(Base):
    """
    Decisions made by agents. Matches CORE v2.2 schema.
    """

    __tablename__ = "agent_decisions"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("core.tasks.id"))
    decision_point: Mapped[str] = mapped_column(Text)
    options_considered: Mapped[dict] = mapped_column(JSONB)
    chosen_option: Mapped[str] = mapped_column(Text)
    reasoning: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2))
    was_correct: Mapped[bool | None] = mapped_column(Boolean)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ID: a2c3d4e5-agent-memory-aligned
# ID: ae0b3160-a30d-4ec7-bad9-fd42c6e940b9
class AgentMemory(Base):
    """
    Short-term and pattern memory for agents. Matches CORE v2.2 schema.
    """

    __tablename__ = "agent_memory"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cognitive_role: Mapped[str] = mapped_column(Text)
    memory_type: Mapped[str] = mapped_column(
        Text
    )  # fact, observation, decision, pattern, error
    content: Mapped[str] = mapped_column(Text)
    related_task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("core.tasks.id")
    )
    relevance_score: Mapped[float] = mapped_column(Numeric(3, 2), default=1.0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# =============================================================================
# SECTION 4: VECTOR INTEGRATION LAYER
# =============================================================================


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


# ID: vector-sync-log-model
# ID: 462a9d2d-a0b6-494c-a22d-6a35bbd0eb95
class VectorSyncLog(Base):
    __tablename__ = "vector_sync_log"
    __table_args__ = {"schema": "core"}

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
    __tablename__ = "retrieval_feedback"
    __table_args__ = {"schema": "core"}

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
    __tablename__ = "semantic_cache"
    __table_args__ = {"schema": "core"}

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


# =============================================================================
# SECTION 5: LEARNING & FEEDBACK
# =============================================================================


# ID: feedback-model
# ID: 9a090789-0e88-48e9-935e-09c25aeaa944
class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = {"schema": "core"}

    id = Column(pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(pgUUID(as_uuid=True), ForeignKey("core.tasks.id"))
    action_id = Column(pgUUID(as_uuid=True), ForeignKey("core.actions.id"))
    feedback_type = Column(Text, nullable=False)
    message = Column(Text, nullable=False)
    corrective_action = Column(Text)
    applied = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# =============================================================================
# SECTION 6: SYSTEM METADATA & ARTIFACTS
# =============================================================================


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


# ID: context-packet-model
# ID: a033727b-4ef6-4cf0-88ce-7db88c1a127e
class ContextPacket(Base):
    """
    Metadata for ContextPackage artifacts. Matches CORE v2.2 schema Section 6A.
    """

    __tablename__ = "context_packets"
    __table_args__ = {"schema": "core"}

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
