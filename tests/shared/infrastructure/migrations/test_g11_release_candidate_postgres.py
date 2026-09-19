# tests/shared/infrastructure/migrations/test_g11_release_candidate_postgres.py
"""URS G11 release-candidate evidence (ADR-162 U8a) on real databases.

G11 -- Upgrade and migration safety -- has four acceptance criteria. Each is
proven here with the real manifest, the real migration files, the committed
release schema fixtures and the real operator route (``core-admin database
migrate --adopt-baseline <tag> --write`` -> ``migrate --write`` -> ``status``):

1. **A formal upgrade path from every released baseline.** v2.9.1 -> current
   and v2.10.1 -> current, independently, ending in ``status`` CURRENT
   (exit 0) with the schema equivalent to a fresh ``schema.sql`` install
   (0 normalised diff lines).
2. **No ``DROP SCHEMA CASCADE``.** The route is delta migration on the
   populated database; the seeded rows below could not survive a drop.
3. **Governance history preserved.** Representative ``blackboard_entries``,
   ``autonomous_proposals`` and ``proposal_consequences`` rows -- fixed ids,
   timestamps, payloads and the proposal->consequence relationship -- are
   compared column by column before and after. The only differences are the
   ones the migrations themselves declare: ``#885`` turns ``draft`` proposals
   ``pending``, and the ``20260722`` backfill ``UPDATE`` fires the
   ``updated_at`` touch trigger on every ``blackboard_entries`` row. Nothing
   else moves; no row is lost; every relationship holds.
4. **A failed migration is rolled back and unrecorded.** Release-level, with
   the real files: the ADR-052 Phase 4 drop refuses on an unaccounted
   ``runtime_settings`` key -- its effects are rolled back, no ledger row is
   written, earlier migrations of the same pass stay recorded; correcting
   the condition lets a retry apply it exactly once; concurrent writers
   still apply each migration exactly once.

The engine-level proofs (synthetic manifest) live in
``test_ledger_engine_postgres.py``; installed-wheel proofs in
``test_wheel_migrate_postgres.py``; the installer's own refusal in
``test_installer_schema_state_postgres.py``.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from shared.infrastructure.repositories.db.common import REPO_ROOT
from shared.infrastructure.repositories.db.ledger_engine import MigrationOutcome
from shared.infrastructure.repositories.db.manifest import load_manifest
from shared.infrastructure.repositories.db.migration_service import (
    MigrationServiceError,
    adopt_baseline,
    migrate_db,
)
from shared.infrastructure.repositories.db.schema_dump import (
    diff_schema_dumps,
    normalise_schema_dump,
)
from shared.infrastructure.repositories.db.schema_gate import (
    SchemaGateState,
    evaluate_schema_gate,
)


if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from .conftest import FreshDatabase


pytestmark = [pytest.mark.integration]

assert REPO_ROOT is not None
SCHEMA_SQL = REPO_ROOT / "schema.sql"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "schema"
BASELINES = ["v2.9.1", "v2.10.1"]

DROP_RS = "20260919e_adr052_phase4_drop_runtime_settings.sql"

# Fixed identities: the point is that exactly these survive.
WORKER = "11111111-1111-4111-8111-111111111111"
BB_FINDING = "aaaaaaaa-0000-4000-8000-000000000001"
BB_REPORT = "aaaaaaaa-0000-4000-8000-000000000002"
BB_RESOLVED = "aaaaaaaa-0000-4000-8000-000000000003"
P_COMPLETED = "bbbbbbbb-0000-4000-8000-000000000001"
P_PENDING = "bbbbbbbb-0000-4000-8000-000000000002"
P_DRAFT = "bbbbbbbb-0000-4000-8000-000000000003"  # v2.9.1 only (#885 retired it)
PID_COMPLETED = "prop-2026-06-01-completed"
PID_PENDING = "prop-2026-06-02-pending"
PID_DRAFT = "prop-2026-06-03-draft"

TABLES = ("blackboard_entries", "autonomous_proposals", "proposal_consequences")
KEY = {
    "blackboard_entries": "id",
    "autonomous_proposals": "id",
    "proposal_consequences": "proposal_id",
}


async def _seed_history(db: FreshDatabase, *, with_draft: bool) -> None:
    await db.execute(
        "insert into core.worker_registry (worker_uuid, worker_name, worker_class, phase, declared_at, last_heartbeat) "
        f"values ('{WORKER}', 'seed_worker', 'SeedWorker', 'EXECUTION', "
        "'2026-06-01T08:00:00+00', '2026-06-01T08:05:00+00')"
    )
    await db.execute(
        "insert into core.blackboard_entries "
        "(id, worker_uuid, entry_type, phase, status, subject, payload, resolution_mechanism, "
        " created_at, updated_at, resolved_at) values "
        f"('{BB_FINDING}', '{WORKER}', 'finding', 'AUDIT', 'open', 'rule.a::src/x.py', "
        ' \'{"rule": "rule.a", "line": 12}\', \'reaudit\', '
        " '2026-06-01T09:00:00+00', '2026-06-01T09:00:00+00', null), "
        f"('{BB_REPORT}', '{WORKER}', 'report', 'EXECUTION', 'resolved', 'sync.db.complete', "
        " '{\"rows\": 42}', null, "
        " '2026-06-01T09:10:00+00', '2026-06-01T09:11:00+00', '2026-06-01T09:11:00+00'), "
        f"('{BB_RESOLVED}', '{WORKER}', 'finding', 'AUDIT', 'resolved', 'rule.b::src/y.py', "
        ' \'{"rule": "rule.b", "line": 3}\', \'self_resolve\', '
        " '2026-06-01T09:20:00+00', '2026-06-02T10:00:00+00', '2026-06-02T10:00:00+00')"
    )
    rows = [
        f"('{P_COMPLETED}', '{PID_COMPLETED}', 'fix rule.b in src/y.py', 'completed', "
        ' \'[{"action": "fix.imports", "file": "src/y.py"}]\', \'{"files": ["src/y.py"]}\', '
        " '2026-06-01T09:30:00+00', 'autonomous', '2026-06-01T09:31:00+00', '2026-06-01T09:32:00+00', "
        " '{\"ok\": true}', true, 'governor', '2026-06-01T09:30:30+00', 'principal.governor', 3, "
        " '2026-06-01T09:32:00+00')",
        f"('{P_PENDING}', '{PID_PENDING}', 'add tests for src/z.py', 'pending', "
        ' \'[{"action": "build.tests", "file": "src/z.py"}]\', \'{"files": ["src/z.py"]}\', '
        " '2026-06-02T11:00:00+00', 'autonomous', null, null, '{}', true, null, null, null, 0, "
        " '2026-06-02T11:00:00+00')",
    ]
    if with_draft:
        rows.append(
            f"('{P_DRAFT}', '{PID_DRAFT}', 'draft goal', 'draft', "
            " '[]', '{}', '2026-06-03T12:00:00+00', 'autonomous', null, null, '{}', false, "
            " null, null, null, 0, '2026-06-03T12:00:00+00')"
        )
    await db.execute(
        "insert into core.autonomous_proposals "
        "(id, proposal_id, goal, status, actions, scope, created_at, created_by, "
        " execution_started_at, execution_completed_at, execution_results, approval_required, "
        " approved_by, approved_at, approval_authority, version, updated_at) values "
        + ", ".join(rows)
    )
    await db.execute(
        "insert into core.proposal_consequences "
        "(proposal_id, recorded_at, pre_execution_sha, post_execution_sha, files_changed, "
        " findings_resolved, authorized_by_rules, declared_production) values "
        f"('{PID_COMPLETED}', '2026-06-01T09:32:05+00', 'aaaa1111', 'bbbb2222', "
        " '[\"src/y.py\"]', '[\"rule.b::src/y.py\"]', '[\"atomic_actions.fix_action_scope\"]', "
        " '[\"src/y.py\"]')"
    )


async def _snapshot(db: FreshDatabase) -> dict[str, dict[str, dict[str, Any]]]:
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for table in TABLES:
        raw = await db.scalar(
            f"select coalesce(jsonb_object_agg({KEY[table]}::text, to_jsonb(t)), '{{}}'::jsonb)::text "
            f"from core.{table} t"
        )
        out[table] = json.loads(str(raw))
    return out


def _core_admin(database_url: str, *args: str) -> tuple[int, str]:
    exe = Path(sys.executable).parent / "core-admin"
    if not exe.is_file():
        pytest.skip("core-admin entry point not installed next to the interpreter")
    env = {
        **{
            k: v
            for k, v in os.environ.items()
            if k not in {"DATABASE_URL", "PYTEST_CURRENT_TEST"}
        },
        "DATABASE_URL": database_url,
    }
    proc = subprocess.run(
        [str(exe), "database", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
        timeout=300,
        check=False,
    )
    return proc.returncode, proc.stdout + proc.stderr


# ── criteria 1-3: both baselines, real route, history preserved ─────────────


@pytest.mark.parametrize("tag", BASELINES)
# ID: ea385b81-b297-474d-b029-bf60d6fd6967
async def test_upgrade_from_released_baseline_preserves_governance_history(
    tag: str,
    database_factory: Callable[[], Awaitable[FreshDatabase]],
    schema_dumper: Callable[[str], str],
) -> None:
    with_draft = tag == "v2.9.1"
    hop = await database_factory()
    await hop.load_schema(FIXTURES / f"schema-{tag}.sql")
    await _seed_history(hop, with_draft=with_draft)
    before = await _snapshot(hop)
    assert len(before["blackboard_entries"]) == 3
    assert len(before["autonomous_proposals"]) == (3 if with_draft else 2)
    assert len(before["proposal_consequences"]) == 1

    # The operator's route, through the real CLI entry point.
    code, out = _core_admin(hop.url, "status", "--format", "json")
    assert code == 2, out[-800:]
    assert (
        json.loads(out[out.index("{") : out.rindex("}") + 1])["baseline_suggestion"]
        == tag
    )

    code, out = _core_admin(hop.url, "migrate", "--adopt-baseline", tag, "--write")
    assert code == 0 and "adopted" in out, out[-800:]
    code, out = _core_admin(hop.url, "migrate", "--write")
    assert code == 0, out[-1200:]
    assert "DROP SCHEMA" not in out
    code, out = _core_admin(hop.url, "status", "--format", "json")
    assert code == 0, out[-800:]
    payload = json.loads(out[out.index("{") : out.rindex("}") + 1])
    assert payload["current"] is True and payload["pending_migrations"] == []
    assert set(payload["applied_migrations"]) == set(load_manifest().order)

    # Criterion 1: equivalent to a fresh install.
    fresh = await database_factory()
    await fresh.load_schema(SCHEMA_SQL)
    diff = diff_schema_dumps(
        normalise_schema_dump(schema_dumper(fresh.name)),
        normalise_schema_dump(schema_dumper(hop.name)),
        expected_label="schema.sql (fresh install)",
        actual_label=f"schema-{tag}.sql + seeded history + manifest replay",
    )
    assert not diff, "\n".join(diff)

    # Criterion 3: every seeded row, column by column.
    after = await _snapshot(hop)
    for table in TABLES:
        assert set(after[table]) == set(before[table]), f"{table}: rows lost or gained"
    for rid, old in before["proposal_consequences"].items():
        new = after["proposal_consequences"][rid]
        assert {k: new[k] for k in old} == old
        assert new["consequence_source"] == "execution"  # 20260717 default
    for rid, old in before["autonomous_proposals"].items():
        new = after["autonomous_proposals"][rid]
        if old["status"] == "draft":
            # Declared by 20260914_885: draft -> pending, updated_at touched.
            assert new["status"] == "pending" and new["updated_at"] > old["updated_at"]
            assert {k: new[k] for k in old if k not in {"status", "updated_at"}} == {
                k: v for k, v in old.items() if k not in {"status", "updated_at"}
            }
        else:
            assert {k: new[k] for k in old} == old, rid
    for rid, old in before["blackboard_entries"].items():
        new = after["blackboard_entries"][rid]
        moved = {k for k in old if new[k] != old[k]}
        if with_draft:
            # v2.9.1 replays 20260722: its backfill UPDATE fires the
            # updated_at touch trigger on every row; nothing else moves.
            assert moved <= {"updated_at"}, f"{rid}: {sorted(moved)}"
            assert new["last_seen_at"] == old["created_at"]
            if old["entry_type"] == "finding":
                assert new["first_payload"] == old["payload"]
            assert new["occurrence_count"] == 1
        else:
            assert not moved, f"{rid}: {sorted(moved)}"
    # Relationship intact: the consequence still joins its proposal.
    assert (
        await hop.scalar(
            "select count(*) from core.proposal_consequences c "
            "join core.autonomous_proposals p using (proposal_id) "
            f"where p.id = '{P_COMPLETED}' and c.post_execution_sha = 'bbbb2222'"
        )
        == 1
    )
    assert (
        await hop.scalar(
            "select count(*) from core.blackboard_entries b join core.worker_registry w using (worker_uuid)"
        )
        == 3
    )


# ── criterion 4: failure rolled back and unrecorded; retry once; concurrency ─


async def _v2_9_1_adopted(db: FreshDatabase) -> None:
    await db.load_schema(FIXTURES / "schema-v2.9.1.sql")
    await adopt_baseline("v2.9.1", write=True, session_factory=db.session_factory)


# ID: f3122384-ad36-4735-b536-06bd53e3e580
async def test_failed_release_migration_is_rolled_back_unrecorded_and_retries_exactly_once(
    fresh_database: FreshDatabase,
) -> None:
    db = fresh_database
    await _v2_9_1_adopted(db)
    await _seed_history(db, with_draft=True)
    await db.execute(
        "insert into core.runtime_settings (key, value, is_secret) values "
        "('core.crypto.master_key', 'k', true)"
    )
    await db.execute(
        "insert into core.config_migration_log "
        "(env_key, source, destination_table, destination_column, imported_at, migrated_at, migrated_by) "
        "values ('core.crypto.master_key', 'runtime_settings', 'pending', 'pending', now(), NULL, 't')"
    )
    pending = (
        await migrate_db(write=False, session_factory=db.session_factory)
    ).pending_before
    assert DROP_RS in pending

    with pytest.raises(MigrationServiceError, match="ADR-052 Phase 4 refused"):
        await migrate_db(write=True, session_factory=db.session_factory)

    # Rolled back: the table and its row are exactly as before; not recorded.
    assert (
        await db.scalar(
            "select value from core.runtime_settings where key = 'core.crypto.master_key'"
        )
        == "k"
    )
    rows = await db.ledger_rows()
    assert DROP_RS not in rows
    # Earlier migrations of the same pass are recorded (per-migration atomicity).
    for earlier in pending[: pending.index(DROP_RS)]:
        assert earlier in rows, earlier
    assert (await evaluate_schema_gate(session_factory=db.session_factory)).state is (
        SchemaGateState.PENDING
    )
    # The seeded history survived the failed pass too.
    assert await db.scalar("select count(*) from core.blackboard_entries") == 3
    assert await db.scalar("select count(*) from core.proposal_consequences") == 1

    # Correct the condition; the retry applies it exactly once.
    await db.execute(
        "update core.config_migration_log set migrated_at = now(), "
        "destination_table = 'secret_store', destination_column = 'value' "
        "where env_key = 'core.crypto.master_key'"
    )
    retry = await migrate_db(write=True, session_factory=db.session_factory)
    assert retry.applied == [DROP_RS]
    assert (
        await db.scalar("select to_regclass('core.runtime_settings') is null") is True
    )
    assert (await evaluate_schema_gate(session_factory=db.session_factory)).state is (
        SchemaGateState.CURRENT
    )
    again = await migrate_db(write=True, session_factory=db.session_factory)
    assert again.pending_before == [] and again.results == []


# ID: 2f7a7b8b-59e1-45b0-a893-d8664b79a10d
async def test_concurrent_release_upgrades_apply_each_migration_exactly_once(
    fresh_database: FreshDatabase,
) -> None:
    db = fresh_database
    await _v2_9_1_adopted(db)
    await _seed_history(db, with_draft=True)
    pending = (
        await migrate_db(write=False, session_factory=db.session_factory)
    ).pending_before
    assert pending

    reports = await asyncio.gather(
        *(migrate_db(write=True, session_factory=db.session_factory) for _ in range(3))
    )
    executed: dict[str, int] = {}
    for report in reports:
        for result in report.results:
            if result.outcome in (
                MigrationOutcome.APPLIED,
                MigrationOutcome.RECONCILED,
            ):
                executed[result.id] = executed.get(result.id, 0) + 1
    assert executed == {m: 1 for m in pending}, executed
    assert set(await db.ledger_rows()) == set(load_manifest().order)
    assert (await evaluate_schema_gate(session_factory=db.session_factory)).state is (
        SchemaGateState.CURRENT
    )
    assert await db.scalar("select count(*) from core.blackboard_entries") == 3
    assert (
        await db.scalar(
            f"select status from core.autonomous_proposals where id = '{P_DRAFT}'"
        )
        == "pending"
    )
