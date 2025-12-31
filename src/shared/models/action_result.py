# src/shared/models/action_result.py

"""
ActionResult Database Model - Audit trail for CORE workflow operations.

Records the outcome of every action (tests, coverage, alignment, code generation, etc.)
to provide workflow gate verification and historical compliance tracking.

Constitutional Principles: knowledge.database_ssot, safe_by_default
"""

from __future__ import annotations

from typing import ClassVar
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as pgUUID

from shared.infrastructure.database.models.knowledge import Base


# ID: 8a9b0c1d-2e3f-4a5b-6c7d-8e9f0a1b2c3d
class ActionResult(Base):
    """
    Records the outcome of CORE operations for workflow gating and audit trails.

    Used by WorkflowGateEngine to verify:
    - Test execution status
    - Coverage measurements
    - Alignment healing outcomes
    - Code generation success/failure
    - Any other quality gate checkpoints
    """

    __tablename__: ClassVar[str] = "action_results"
    __table_args__: ClassVar[dict] = {"schema": "core"}

    id = Column(pgUUID(as_uuid=True), primary_key=True, default=uuid4)
    action_type = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Type: test_execution, alignment, code_generation, coverage_check, etc.",
    )
    ok = Column(
        Boolean,
        nullable=False,
        index=True,
        comment="Whether the action succeeded (True) or failed (False)",
    )
    file_path = Column(
        String(500),
        nullable=True,
        index=True,
        comment="Target file path if action was file-specific",
    )
    error_message = Column(Text, nullable=True, comment="Error details if ok=False")
    action_metadata = Column(
        JSONB,
        nullable=True,
        comment="Additional context: coverage_percent, test_count, violations_fixed, etc.",
    )
    agent_id = Column(
        String(100), nullable=True, comment="Which agent/service performed the action"
    )
    duration_ms = Column(
        Integer, nullable=True, comment="How long the action took in milliseconds"
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    def __repr__(self) -> str:
        status = "✓" if self.ok else "✗"
        return f"<ActionResult {status} {self.action_type} @ {self.created_at}>"
