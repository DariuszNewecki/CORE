# src/shared/infrastructure/database/models/governance.py
"""
Governance Layer models for CORE v2.2 Schema.
Section 2: Audits and Constitutional Violations.
"""

from __future__ import annotations

import uuid
from typing import ClassVar

from sqlalchemy import (
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
from sqlalchemy.dialects.postgresql import UUID as pgUUID

from .knowledge import Base


# ID: ea32fc95-90ef-4735-86c0-f09ebc280a5f
class AuditRun(Base):
    __tablename__: ClassVar[str] = "audit_runs"
    __table_args__: ClassVar[dict] = {"schema": "core"}

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


# ID: c1c88088-6e9e-4400-907b-578e380c8113
class ConstitutionalViolation(Base):
    __tablename__: ClassVar[str] = "constitutional_violations"
    __table_args__: ClassVar[dict] = {"schema": "core"}

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
