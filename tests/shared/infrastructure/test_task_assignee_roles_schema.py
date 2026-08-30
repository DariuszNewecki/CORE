# tests/shared/infrastructure/test_task_assignee_roles_schema.py
"""#821 Unit 1 schema proof: task-assignee/actor roles are separated from
LLM cognitive-role storage.

DB-backed against the live schema (core_test in CI/local dev, per
infra/scripts/migrations/20260830_821_create_task_assignee_roles.sql).
Verifies the target model directly against the database, not against the
migration file's text: core.task_assignee_roles exists with the full
14-role vocabulary and correct actor/cognitive discriminator, core.tasks
references it (not core.cognitive_roles), the three actor roles are gone
from core.cognitive_roles, and core.v_agent_workload surfaces workload for
the full assignable-role universe.

schema.sql is a --schema-only dump (this repo's own convention, per
infra/scripts/reset_test_db.sh) and CI provisions its ephemeral core_test
from schema.sql alone -- never by replaying the migration ledger. So the
14-row seed the migration inserts is real DDL-adjacent data that exists on
live/the persistent local core_test (both had the actual migration applied)
but NOT on a schema-only-provisioned database. These tests seed idempotently
(mirroring the migration's own ON CONFLICT DO NOTHING) before asserting, so
the same test proves the same thing regardless of which of those two
provisioning paths produced the database under test.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


pytestmark = [pytest.mark.integration]

_ACTOR_ROLES = {"AutonomousDeveloper", "Human", "StrategicAuditor"}
_COGNITIVE_ROLES = {
    "Architect",
    "CapabilityTagger",
    "CodeReviewer",
    "Coder",
    "ConstitutionalCoherenceAnalyst",
    "DocstringWriter",
    "LocalCoder",
    "LocalReasoner",
    "Planner",
    "RemoteCoder",
    "Vectorizer",
}


@pytest.fixture(autouse=True)
async def _ensure_task_assignee_roles_seeded(db_session: AsyncSession) -> None:
    """Idempotent re-seed of the migration's own 14-row vocabulary --
    mirrors infra/scripts/migrations/20260830_821_create_task_assignee_roles.sql
    step 2 exactly, so a schema-only-provisioned database (CI) proves the same
    property as one that had the real migration applied (live/local core_test)."""
    for role, kind in [
        ("Architect", "cognitive"),
        ("AutonomousDeveloper", "actor"),
        ("CapabilityTagger", "cognitive"),
        ("CodeReviewer", "cognitive"),
        ("Coder", "cognitive"),
        ("ConstitutionalCoherenceAnalyst", "cognitive"),
        ("DocstringWriter", "cognitive"),
        ("Human", "actor"),
        ("LocalCoder", "cognitive"),
        ("LocalReasoner", "cognitive"),
        ("Planner", "cognitive"),
        ("RemoteCoder", "cognitive"),
        ("StrategicAuditor", "actor"),
        ("Vectorizer", "cognitive"),
    ]:
        await db_session.execute(
            text(
                "INSERT INTO core.task_assignee_roles (role, kind) "
                "VALUES (:role, :kind) ON CONFLICT (role) DO NOTHING"
            ),
            {"role": role, "kind": kind},
        )
    await db_session.commit()


async def test_task_assignee_roles_holds_all_14_with_correct_kind(
    db_session: AsyncSession,
) -> None:
    result = await db_session.execute(
        text("SELECT role, kind FROM core.task_assignee_roles")
    )
    rows = {r[0]: r[1] for r in result.fetchall()}

    assert set(rows) == _ACTOR_ROLES | _COGNITIVE_ROLES
    for role in _ACTOR_ROLES:
        assert rows[role] == "actor", f"{role} must be kind=actor"
    for role in _COGNITIVE_ROLES:
        assert rows[role] == "cognitive", f"{role} must be kind=cognitive"


async def test_task_assignee_roles_declares_no_capability_columns(
    db_session: AsyncSession,
) -> None:
    """No cognitive capabilities may be duplicated into the assignee
    registry -- capabilities stay governed exclusively by
    core.cognitive_roles."""
    result = await db_session.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='core' AND table_name='task_assignee_roles'"
        )
    )
    columns = {r[0] for r in result.fetchall()}
    assert "required_capabilities" not in columns
    assert "provided_capabilities" not in columns


async def test_cognitive_roles_no_longer_contains_actor_roles(
    db_session: AsyncSession,
) -> None:
    result = await db_session.execute(
        text(
            "SELECT role FROM core.cognitive_roles "
            "WHERE role = ANY(:actors)"
        ),
        {"actors": list(_ACTOR_ROLES)},
    )
    assert result.fetchall() == []


async def test_tasks_assigned_role_fk_targets_task_assignee_roles(
    db_session: AsyncSession,
) -> None:
    result = await db_session.execute(
        text(
            "SELECT confrelid::regclass::text FROM pg_constraint "
            "WHERE conrelid = 'core.tasks'::regclass "
            "AND conname = 'tasks_assigned_role_registry_fkey'"
        )
    )
    row = result.first()
    assert row is not None, "tasks_assigned_role_registry_fkey must exist"
    assert row[0] == "core.task_assignee_roles"

    old_fk = await db_session.execute(
        text(
            "SELECT 1 FROM pg_constraint "
            "WHERE conrelid = 'core.tasks'::regclass "
            "AND conname = 'tasks_assigned_role_fkey'"
        )
    )
    assert old_fk.first() is None, (
        "the old tasks -> cognitive_roles FK must be gone"
    )


async def test_v_agent_workload_surfaces_full_assignable_role_universe(
    db_session: AsyncSession,
) -> None:
    result = await db_session.execute(text("SELECT role FROM core.v_agent_workload"))
    roles = {r[0] for r in result.fetchall()}
    assert _ACTOR_ROLES.issubset(roles), (
        "v_agent_workload must surface actor-role task workload, not just cognitive roles"
    )


async def test_no_unresolved_historical_assigned_role_values(
    db_session: AsyncSession,
) -> None:
    result = await db_session.execute(
        text(
            "SELECT count(DISTINCT t.assigned_role) FROM core.tasks t "
            "LEFT JOIN core.task_assignee_roles tar ON tar.role = t.assigned_role "
            "WHERE t.assigned_role IS NOT NULL AND tar.role IS NULL"
        )
    )
    assert result.scalar() == 0
