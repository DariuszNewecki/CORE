# src/shared/infrastructure/database/models/governance.py
"""
Governance Layer models for CORE v2.2 Schema.
Section 2: Audits and Constitutional Violations.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
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

from .knowledge import Base


# ID: ea32fc95-90ef-4735-86c0-f09ebc280a5f
class AuditRun(Base):
    __tablename__ = "audit_runs"
    __table_args__ = ({"schema": "core"},)

    run_id = Column(pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(Text, nullable=False, server_default="manual")
    commit_sha = Column(String(40))
    verdict = Column(Text, nullable=False, server_default="pending")
    status = Column(Text, nullable=False, server_default="pending")
    score = Column(Numeric(4, 3))
    finding_count = Column(Integer, nullable=False, server_default="0")
    blocking_count = Column(Integer, nullable=False, server_default="0")
    started_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at = Column(DateTime(timezone=True))
    findings = Column(JSONB)


# ID: 60cc8c86-76c9-4279-9a73-326f9058fdb3
class FixRun(Base):
    __tablename__ = "fix_runs"
    __table_args__ = ({"schema": "core"},)

    id = Column(pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind = Column(Text, nullable=False)
    fix_id = Column(Text)
    target_files = Column(JSONB)
    write = Column(Boolean, nullable=False)
    status = Column(Text, nullable=False, server_default="pending")
    requested_by = Column(Text, nullable=False)
    requested_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    result = Column(JSONB)
    error = Column(Text)


# ID: a1c4d6e8-9b3f-4f72-a5c1-7d09b3e2f481
class CoverageRun(Base):
    __tablename__ = "coverage_runs"
    __table_args__ = ({"schema": "core"},)

    id = Column(pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_file = Column(Text)
    batch_priority = Column(Text)
    write = Column(Boolean, nullable=False, server_default="false")
    status = Column(Text, nullable=False, server_default="pending")
    requested_by = Column(Text, nullable=False)
    requested_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    result = Column(JSONB)
    error = Column(Text)


# ID: 7e25b3f4-19d8-4a26-bd8f-c63a5e21d70c
class RefactorRun(Base):
    __tablename__ = "refactor_runs"
    __table_args__ = ({"schema": "core"},)

    id = Column(pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    goal = Column(Text, nullable=False)
    write = Column(Boolean, nullable=False, server_default="false")
    status = Column(Text, nullable=False, server_default="pending")
    requested_by = Column(Text, nullable=False)
    requested_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    result = Column(JSONB)
    error = Column(Text)


# ID: 4f1a9c83-d6e5-42b7-a7f6-2b0e9f6f0a13
class AuditRemediationRun(Base):
    __tablename__ = "audit_remediation_runs"
    __table_args__ = ({"schema": "core"},)

    id = Column(pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_run_id = Column(pgUUID(as_uuid=True), ForeignKey("core.audit_runs.run_id"))
    mode = Column(Text, nullable=False)
    write = Column(Boolean, nullable=False, server_default="false")
    status = Column(Text, nullable=False, server_default="pending")
    requested_by = Column(Text, nullable=False)
    requested_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    result = Column(JSONB)
    error = Column(Text)


# ID: 5b8a2e9c-3d1f-4a7b-8c0d-6e9f1a2b3c4e
class CensusRun(Base):
    __tablename__ = "census_runs"
    __table_args__ = ({"schema": "core"},)

    id = Column(pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot = Column(Boolean, nullable=False, server_default="false")
    baseline_name = Column(Text)
    status = Column(Text, nullable=False, server_default="pending")
    requested_by = Column(Text, nullable=False)
    requested_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    result = Column(JSONB)
    error = Column(Text)


# ID: 6c9b3f0d-4e2a-4b8c-9d1e-7f0a2b3c4d5f
class SyncRun(Base):
    __tablename__ = "sync_runs"
    __table_args__ = ({"schema": "core"},)

    id = Column(pgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sync_type = Column(Text, nullable=False)
    write = Column(Boolean, nullable=False, server_default="false")
    target = Column(Text)
    status = Column(Text, nullable=False, server_default="pending")
    requested_by = Column(Text, nullable=False)
    requested_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    result = Column(JSONB)
    error = Column(Text)


# ID: c1c88088-6e9e-4400-907b-578e380c8113
class ConstitutionalViolation(Base):
    __tablename__ = "constitutional_violations"
    __table_args__ = ({"schema": "core"},)

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
