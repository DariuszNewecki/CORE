# src/shared/infrastructure/database/models/llm_config.py

"""LLM configuration domain models — Phase 1 of ADR-052.

Tables introduced by the migration
`infra/scripts/migrations/20260516_adr_052_phase1_llm_config_schema.sql`:

* role_resource_assignments — priority-ordered role → resource mapping
* system_config             — typed singleton for system-wide flags
* secret_store              — typed credential store
* config_migration_log      — .env → final-table audit trail
* capability_alignment_tests, model_performance_results
                            — benchmark registry
* llm_exchange_log          — append-only LLM-interaction record,
                              partitioned monthly on `ts`

Phase 1 lands the schema without readers. Phase 2 populates these
tables from `runtime_settings`; Phase 3 cuts `ConfigService` over to
them.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as pgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .knowledge import Base


# ID: a14ebb12-d825-41fe-8a14-31e0c28eee2f
class RoleResourceAssignment(Base):
    """Priority-ordered binding between a cognitive role and an LLM resource.

    Replaces the single `cognitive_roles.assigned_resource` FK with a
    list that supports primary + secondary fallback (priority >= 1, with
    a partial unique index on (role, priority) WHERE is_active).
    """

    __tablename__: ClassVar[str] = "role_resource_assignments"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    role: Mapped[str] = mapped_column(
        Text,
        ForeignKey("core.cognitive_roles.role", onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True,
    )
    resource: Mapped[str] = mapped_column(
        Text,
        ForeignKey("core.llm_resources.name", onupdate="CASCADE", ondelete="RESTRICT"),
        primary_key=True,
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ID: a6e328e9-cf54-4363-9fdd-163f141338a6
class SystemConfig(Base):
    """Typed singleton for system-wide configuration.

    One canonical row. Collapses the three duplicate `llm_enabled` keys
    in `runtime_settings` and holds the system-default `operating_mode`
    (overridable per role in `cognitive_roles.operating_mode`).
    """

    __tablename__: ClassVar[str] = "system_config"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    operating_mode: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="local_only"
    )
    llm_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    request_timeout_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="300"
    )
    embed_model_revision: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ID: d127e44b-7519-420b-a6ad-01d230ba477a
class SecretStore(Base):
    """Typed replacement for `runtime_settings` rows where `is_secret=true`.

    Key convention preserved: `{env_prefix}.api_key`. The `resource_name`
    FK enables "list all credentials for a resource" without parsing the
    key string.
    """

    __tablename__: ClassVar[str] = "secret_store"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    resource_name: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("core.llm_resources.name", onupdate="CASCADE", ondelete="SET NULL"),
    )
    value: Mapped[str] = mapped_column(Text, nullable=False)
    last_rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ID: e36bd25a-0adc-41c7-9517-8d4a65d7efa3
class ConfigMigrationLog(Base):
    """Audit trail for the `.env` → `runtime_settings` → final-table journey.

    `imported_at` records when the value first landed in `runtime_settings`.
    `migrated_at` records when Phase 2 moved it to its typed home; NULL
    means the row is still in transit. `runtime_settings` may be dropped
    once every row carries a non-null `migrated_at`.
    """

    __tablename__: ClassVar[str] = "config_migration_log"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    env_key: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    destination_table: Mapped[str] = mapped_column(Text, nullable=False)
    destination_column: Mapped[str] = mapped_column(Text, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    migrated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    migrated_by: Mapped[str] = mapped_column(Text, nullable=False)


# ID: e5134b7c-031a-48b4-8630-8b1c6654a0a2
class CapabilityAlignmentTest(Base):
    """Benchmark test suite definition.

    Each row defines one test that capability alignment can be scored
    against. `capability` references the canonical capability taxonomy
    in `.intent/`.
    """

    __tablename__: ClassVar[str] = "capability_alignment_tests"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    capability: Mapped[str] = mapped_column(Text, nullable=False)
    expected_behavior: Mapped[str] = mapped_column(Text, nullable=False)
    scoring_rubric: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ID: 4886f220-cce8-4246-b05b-81d2dfea8e61
class ModelPerformanceResult(Base):
    """Per-model benchmark scores.

    Triggered on resource registration (`triggered_by='registration'`,
    one row per (resource, test) — partial unique index enforces this),
    or run manually / on schedule (unrestricted).
    """

    __tablename__: ClassVar[str] = "model_performance_results"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    resource_name: Mapped[str] = mapped_column(
        Text,
        ForeignKey("core.llm_resources.name", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    test_id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True),
        ForeignKey("core.capability_alignment_tests.id", ondelete="RESTRICT"),
        nullable=False,
    )
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    triggered_by: Mapped[str] = mapped_column(Text, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ID: 4c826e1e-4b81-4b11-8ed9-eaa9d3632916
class LlmExchangeLog(Base):
    """Append-only record of every CORE-LLM interaction.

    Partitioned monthly by `ts` (see ADR-052). The partition key forces
    the PK to be composite `(id, ts)` rather than `(id)` alone, because
    PostgreSQL requires every unique constraint on a partitioned table
    to include the partitioning columns. Application code keys on `id`
    only; the composite is transparent to readers.
    """

    __tablename__: ClassVar[str] = "llm_exchange_log"
    __table_args__: ClassVar[dict[str, Any]] = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        pgUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    resource_name: Mapped[str] = mapped_column(
        Text,
        ForeignKey("core.llm_resources.name", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    cognitive_role: Mapped[str] = mapped_column(
        Text,
        ForeignKey(
            "core.cognitive_roles.role", onupdate="CASCADE", ondelete="RESTRICT"
        ),
        nullable=False,
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        pgUUID(as_uuid=True),
        ForeignKey("core.tasks.id", ondelete="SET NULL"),
    )
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    model_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    cost_estimate: Mapped[float | None] = mapped_column(Numeric(10, 6))
    privacy_level: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="standard"
    )
    redacted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
        nullable=False,
        server_default=func.now(),
    )
