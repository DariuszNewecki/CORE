# tests/shared/infrastructure/migrations/test_backfill_reconstruction_postgres.py
"""ADR-162 U5a — the four historical backfill migrations on real databases.

The v2.9.1..v2.10.1 span changed the live schema without migration files:
``core_archive`` (ADR-052 archiver, runtime-created), ``audit_findings.run_id``
(ADR-054 amendment 2026-07-07, #345), ``users.display_name`` (out of band)
and the ``runtime_settings`` drop (ADR-052 Phase 4, gated on a complete
``config_migration_log``). Proven here with the real manifest and files:

* on a v2.9.1 database every backfill executes and the result is current;
* on a v2.10.1-shaped database every backfill is reconciled — no DDL re-run;
* partially applied states converge (structure half-present) without loss;
* pre-#345 ``audit_findings`` rows are preserved under one labelled run;
* populated ``runtime_settings`` with an unmigrated key refuses — naming the
  key, recording nothing — while fully migrated/retired keys let the drop
  proceed, ``config_migration_log`` retained as the audit trail;
* re-running is a no-op;
* (U5b) a same-named object of the wrong shape — an index on the wrong
  columns, an FK to the wrong relation, a NOT NULL ``display_name`` — is not
  the postcondition: it does not reconcile, the migration's ``IF NOT EXISTS``
  DDL cannot repair it, the post-probe fails, the engine rolls back, the
  malformed structure is left exactly as found and no ledger row is written.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from shared.infrastructure.repositories.db.common import REPO_ROOT
from shared.infrastructure.repositories.db.ledger_engine import (
    LedgerEngineError,
    MigrationOutcome,
    apply_migration,
    ensure_ledger,
)
from shared.infrastructure.repositories.db.manifest import load_manifest
from shared.infrastructure.repositories.db.migration_service import (
    MigrationServiceError,
    adopt_baseline,
    migrate_db,
)
from shared.infrastructure.repositories.db.schema_gate import (
    SchemaGateState,
    evaluate_schema_gate,
)


if TYPE_CHECKING:
    from .conftest import FreshDatabase


pytestmark = [pytest.mark.integration]

assert REPO_ROOT is not None
SCHEMA_V2_9_1 = REPO_ROOT / "tests" / "fixtures" / "schema" / "schema-v2.9.1.sql"
SCHEMA_V2_10_1 = REPO_ROOT / "tests" / "fixtures" / "schema" / "schema-v2.10.1.sql"

CORE_ARCHIVE = "20260919b_adr052_core_archive_schema.sql"
RUN_ID = "20260919c_adr054_audit_findings_run_id.sql"
DISPLAY_NAME = "20260919d_users_display_name.sql"
DROP_RS = "20260919e_adr052_phase4_drop_runtime_settings.sql"
BACKFILLS = [CORE_ARCHIVE, RUN_ID, DISPLAY_NAME, DROP_RS]


async def _apply(db: FreshDatabase, mig_id: str) -> MigrationOutcome:
    manifest = load_manifest()
    result = await apply_migration(
        manifest.entry(mig_id),
        manifest.sql_path(mig_id, Path(str(REPO_ROOT))),
        session_factory=db.session_factory,
    )
    return result.outcome


async def _v2_9_1_upgraded_through_v2_10_1(db: FreshDatabase) -> None:
    """A v2.9.1 database brought up to the v2.10.1 baseline: only the ledger
    column and the four backfills remain pending."""
    await db.load_schema(SCHEMA_V2_9_1)
    await adopt_baseline("v2.9.1", write=True, session_factory=db.session_factory)


# ── v2.9.1: everything executes ──────────────────────────────────────────────


# ID: 4b24bd3a-2400-456e-adb9-46a9c14fa6cc
async def test_v2_9_1_executes_every_backfill_and_becomes_current(
    fresh_database: FreshDatabase,
) -> None:
    db = fresh_database
    await _v2_9_1_upgraded_through_v2_10_1(db)
    before = await evaluate_schema_gate(session_factory=db.session_factory)
    assert before.state is SchemaGateState.PENDING
    assert all(b in before.details["pending"] for b in BACKFILLS)

    report = await migrate_db(write=True, session_factory=db.session_factory)
    assert all(b in report.applied for b in BACKFILLS)
    assert report.reconciled == []

    assert (
        await db.scalar("select to_regclass('core.runtime_settings') is null") is True
    )
    assert await db.scalar(
        "select exists (select 1 from pg_namespace where nspname='core_archive')"
    )
    after = await evaluate_schema_gate(session_factory=db.session_factory)
    assert after.state is SchemaGateState.CURRENT
    again = await migrate_db(write=True, session_factory=db.session_factory)
    assert again.pending_before == [] and again.results == []


# ── v2.10.1: everything reconciles, no DDL ───────────────────────────────────


# ID: 769c02ff-196d-4e81-8af7-73fd4db36b2b
async def test_v2_10_1_reconciles_every_backfill_without_executing_ddl(
    fresh_database: FreshDatabase,
) -> None:
    db = fresh_database
    await db.load_schema(SCHEMA_V2_10_1)
    await adopt_baseline("v2.10.1", write=True, session_factory=db.session_factory)
    report = await migrate_db(write=True, session_factory=db.session_factory)
    by_id = {r.id: r for r in report.results}
    for b in BACKFILLS:
        assert by_id[b].outcome is MigrationOutcome.RECONCILED, b
        assert by_id[b].statements_executed == 0, b
    rows = await db.ledger_rows()
    assert all(rows[b] for b in BACKFILLS)
    assert (await evaluate_schema_gate(session_factory=db.session_factory)).state is (
        SchemaGateState.CURRENT
    )


# ── partially applied states converge ────────────────────────────────────────


# ID: 0b93269f-374d-42fb-8e0f-063d76645635
async def test_partially_applied_run_id_state_converges(
    fresh_database: FreshDatabase,
) -> None:
    """Column present but nullable, no FK, two of four indexes: the probe is
    false, so the migration executes and completes the structure without
    touching existing rows."""
    db = fresh_database
    await _v2_9_1_upgraded_through_v2_10_1(db)
    await db.execute("alter table core.audit_findings add column run_id uuid")
    await db.execute(
        "create index idx_audit_findings_run_id on core.audit_findings (run_id)"
    )
    await db.execute("insert into core.audit_runs (source) values ('cli')")
    await db.execute(
        "insert into core.audit_findings (run_id, check_id, severity, message) "
        "select run_id, 'c', 'info', 'm' from core.audit_runs"
    )
    assert await _apply(db, RUN_ID) is MigrationOutcome.APPLIED
    assert await db.scalar("select count(*) from core.audit_findings") == 1
    assert (
        await db.scalar("select count(*) from core.audit_runs") == 1
    )  # no synthetic run
    assert (
        await db.scalar(
            "select count(*) from pg_indexes where tablename='audit_findings' "
            "and indexname like 'idx_audit_findings_%run%'"
        )
        == 4
    )
    assert await _apply(db, RUN_ID) is MigrationOutcome.SKIPPED_RECORDED


# ID: 8c48b40a-13e5-400c-9f7c-d630c81a9467
async def test_partially_applied_schema_and_column_states_converge(
    fresh_database: FreshDatabase,
) -> None:
    db = fresh_database
    await _v2_9_1_upgraded_through_v2_10_1(db)
    await db.execute("create schema core_archive")  # already there by hand
    # core_archive: probe true -> reconciled; display_name: absent -> applied.
    assert await _apply(db, CORE_ARCHIVE) is MigrationOutcome.RECONCILED
    assert await _apply(db, DISPLAY_NAME) is MigrationOutcome.APPLIED
    assert await db.scalar(
        "select exists (select 1 from information_schema.columns where "
        "table_schema='core' and table_name='users' and column_name='display_name')"
    )


# ── pre-#345 audit_findings rows are preserved ──────────────────────────────


# ID: eca29a6d-4790-4e45-91db-2cfaa08fe3b4
async def test_orphan_audit_findings_are_preserved_under_a_labelled_run(
    fresh_database: FreshDatabase,
) -> None:
    db = fresh_database
    await _v2_9_1_upgraded_through_v2_10_1(db)
    await db.execute(
        "insert into core.audit_findings (check_id, severity, message, file_path) values "
        "('rule.a', 'block', 'm1', 'a.py'), ('rule.b', 'info', 'm2', 'b.py'), "
        "('rule.c', 'high', 'm3', 'c.py')"
    )
    assert await _apply(db, RUN_ID) is MigrationOutcome.APPLIED
    assert await db.scalar("select count(*) from core.audit_findings") == 3
    assert (
        await db.scalar("select count(*) from core.audit_findings where run_id is null")
        == 0
    )
    run = await db.scalar(
        "select row_to_json(r)::text from core.audit_runs r "
        "where source = 'pre_adr054_scratch_backfill'"
    )
    assert run is not None
    payload = json.loads(str(run))
    assert payload["verdict"] == "unknown" and payload["status"] == "completed"
    assert payload["finding_count"] == 3 and payload["blocking_count"] == 1
    assert (
        await db.scalar(
            "select count(distinct run_id) from core.audit_findings f "
            "join core.audit_runs r using (run_id) where r.source = 'pre_adr054_scratch_backfill'"
        )
        == 1
    )


# ── runtime_settings: the encoded ADR-052 Phase 4 gate ──────────────────────


async def _seed_runtime_settings(db: FreshDatabase) -> None:
    await db.execute(
        "insert into core.runtime_settings (key, value, is_secret) values "
        "('llm.enabled', 'true', false), ('OLLAMA.api_key', 's', true), "
        "('core.crypto.master_key', 'k', true)"
    )


# ID: a9b5fca7-87af-4d51-b3bd-97b69fd5eeca
async def test_populated_runtime_settings_with_unmigrated_keys_refuses_and_records_nothing(
    fresh_database: FreshDatabase,
) -> None:
    db = fresh_database
    await _v2_9_1_upgraded_through_v2_10_1(db)
    await _seed_runtime_settings(db)
    # Two keys migrated, one (the master key) still pending in the log.
    await db.execute(
        "insert into core.config_migration_log "
        "(env_key, source, destination_table, destination_column, imported_at, migrated_at, migrated_by) values "
        "('llm.enabled', 'runtime_settings', 'system_config', 'llm_enabled', now(), now(), 't'), "
        "('OLLAMA.api_key', 'runtime_settings', 'secret_store', 'value', now(), now(), 't'), "
        "('core.crypto.master_key', 'runtime_settings', 'pending', 'pending', now(), NULL, 't')"
    )
    with pytest.raises(MigrationServiceError) as excinfo:
        await migrate_db(write=True, session_factory=db.session_factory)
    message = str(excinfo.value)
    assert "ADR-052 Phase 4 refused" in message
    assert "core.crypto.master_key" in message
    assert "llm.enabled" not in message  # migrated keys are not blamed
    assert "rolled back; not recorded" in message
    assert await db.scalar("select count(*) from core.runtime_settings") == 3
    assert DROP_RS not in await db.ledger_rows()
    # Earlier backfills in the same pass are recorded (per-migration atomicity).
    rows = await db.ledger_rows()
    assert CORE_ARCHIVE in rows and RUN_ID in rows and DISPLAY_NAME in rows


# ID: c45acad9-b20e-4c6a-b759-3f45ed2755c1
async def test_runtime_settings_key_without_any_log_row_refuses(
    fresh_database: FreshDatabase,
) -> None:
    db = fresh_database
    await _v2_9_1_upgraded_through_v2_10_1(db)
    await db.execute(
        "insert into core.runtime_settings (key, value) values ('added.after.phase1', 'x')"
    )
    with pytest.raises(MigrationServiceError, match=r"added\.after\.phase1"):
        await _apply_via_service(db)
    assert await db.scalar("select count(*) from core.runtime_settings") == 1


async def _apply_via_service(db: FreshDatabase) -> None:
    await migrate_db(write=True, session_factory=db.session_factory)


# ID: 49a0113e-f88a-44e8-a4ec-16210cb69786
async def test_fully_migrated_runtime_settings_is_dropped_and_the_log_retained(
    fresh_database: FreshDatabase,
) -> None:
    db = fresh_database
    await _v2_9_1_upgraded_through_v2_10_1(db)
    await _seed_runtime_settings(db)
    await db.execute(
        "insert into core.config_migration_log "
        "(env_key, source, destination_table, destination_column, imported_at, migrated_at, migrated_by) values "
        "('llm.enabled', 'runtime_settings', 'system_config', 'llm_enabled', now(), now(), 't'), "
        "('OLLAMA.api_key', 'runtime_settings', 'secret_store', 'value', now(), now(), 't'), "
        "('core.crypto.master_key', 'runtime_settings', 'secret_store', 'value', now(), now(), 't')"
    )
    report = await migrate_db(write=True, session_factory=db.session_factory)
    assert DROP_RS in report.applied
    assert (
        await db.scalar("select to_regclass('core.runtime_settings') is null") is True
    )
    assert await db.scalar("select count(*) from core.config_migration_log") == 3
    assert (await evaluate_schema_gate(session_factory=db.session_factory)).state is (
        SchemaGateState.CURRENT
    )


# ID: 46814e00-5152-4746-8329-e83f2e0e7a76
async def test_empty_runtime_settings_is_dropped(fresh_database: FreshDatabase) -> None:
    """A fresh v2.9.1 install has the table with no rows: nothing to account for."""
    db = fresh_database
    await _v2_9_1_upgraded_through_v2_10_1(db)
    await ensure_ledger(db.session_factory)
    assert await _apply(db, DROP_RS) is MigrationOutcome.APPLIED
    assert (
        await db.scalar("select to_regclass('core.runtime_settings') is null") is True
    )


# ── U5b: same-named objects of the wrong shape do not reconcile ─────────────


async def _v2_10_1_shaped(db: FreshDatabase) -> None:
    """A v2.10.1 database: every backfill's structure is present, so on the
    canonical shape all four reconcile (see the v2.10.1 test above)."""
    await db.load_schema(SCHEMA_V2_10_1)
    await adopt_baseline("v2.10.1", write=True, session_factory=db.session_factory)


async def _indexdef(db: FreshDatabase, name: str) -> str:
    return str(
        await db.scalar(
            "select pg_get_indexdef(i.indexrelid) from pg_index i "
            "join pg_class c on c.oid = i.indexrelid "
            f"where i.indrelid = 'core.audit_findings'::regclass and c.relname = '{name}'"
        )
    )


async def _fkdef(db: FreshDatabase) -> str:
    return str(
        await db.scalar(
            "select pg_get_constraintdef(oid) from pg_constraint "
            "where conrelid = 'core.audit_findings'::regclass "
            "and conname = 'audit_findings_run_id_fkey'"
        )
    )


# ID: 51d6b499-0f24-4c4e-9cac-cd89bd688897
async def test_same_named_index_with_wrong_columns_does_not_reconcile(
    fresh_database: FreshDatabase,
) -> None:
    db = fresh_database
    await _v2_10_1_shaped(db)
    await db.execute("drop index core.idx_audit_findings_run_severity")
    await db.execute(
        "create index idx_audit_findings_run_severity "
        "on core.audit_findings using btree (severity)"
    )
    before = await _indexdef(db, "idx_audit_findings_run_severity")
    assert before.endswith("(severity)")

    with pytest.raises(LedgerEngineError, match="verify probe still fails"):
        await _apply(db, RUN_ID)

    # Nothing repaired, nothing recorded: the wrong index is exactly as found.
    assert await _indexdef(db, "idx_audit_findings_run_severity") == before
    assert RUN_ID not in await db.ledger_rows()
    assert (await evaluate_schema_gate(session_factory=db.session_factory)).state is (
        SchemaGateState.PENDING
    )


# ID: 4eeeb81d-2763-48cf-b8de-8e78e013136c
async def test_same_named_fk_to_the_wrong_relation_does_not_reconcile(
    fresh_database: FreshDatabase,
) -> None:
    db = fresh_database
    await _v2_10_1_shaped(db)
    await db.execute(
        "alter table core.audit_findings drop constraint audit_findings_run_id_fkey"
    )
    await db.execute(
        "alter table core.audit_findings add constraint audit_findings_run_id_fkey "
        "foreign key (run_id) references core.autonomous_proposals(id)"
    )
    before = await _fkdef(db)
    assert "autonomous_proposals" in before

    # Through the service: the refusal is a MigrationServiceError, the
    # backfills before it in manifest order are still recorded (per-migration
    # atomicity) and the ones after it are not reached.
    with pytest.raises(MigrationServiceError, match="verify probe still fails"):
        await migrate_db(write=True, session_factory=db.session_factory)

    assert await _fkdef(db) == before
    rows = await db.ledger_rows()
    assert CORE_ARCHIVE in rows
    assert RUN_ID not in rows and DISPLAY_NAME not in rows and DROP_RS not in rows


# ID: 53d9eebd-8a0b-4600-bc1e-e7f1d310c722
async def test_same_named_fk_with_wrong_action_semantics_does_not_reconcile(
    fresh_database: FreshDatabase,
) -> None:
    """Right relation, wrong behaviour: ON DELETE CASCADE is not the canonical
    (NO ACTION, non-deferrable, validated) constraint."""
    db = fresh_database
    await _v2_10_1_shaped(db)
    await db.execute(
        "alter table core.audit_findings drop constraint audit_findings_run_id_fkey"
    )
    await db.execute(
        "alter table core.audit_findings add constraint audit_findings_run_id_fkey "
        "foreign key (run_id) references core.audit_runs(run_id) on delete cascade"
    )
    before = await _fkdef(db)
    with pytest.raises(LedgerEngineError, match="verify probe still fails"):
        await _apply(db, RUN_ID)
    assert await _fkdef(db) == before
    assert RUN_ID not in await db.ledger_rows()


# ID: 005019f9-6b32-4751-992e-542c1c63eedb
async def test_display_name_not_null_does_not_reconcile_as_the_nullable_column(
    fresh_database: FreshDatabase,
) -> None:
    db = fresh_database
    await _v2_10_1_shaped(db)
    await db.execute("alter table core.users alter column display_name set not null")

    with pytest.raises(LedgerEngineError, match="verify probe still fails"):
        await _apply(db, DISPLAY_NAME)

    assert (
        await db.scalar(
            "select is_nullable from information_schema.columns where "
            "table_schema='core' and table_name='users' and column_name='display_name'"
        )
        == "NO"
    )
    assert DISPLAY_NAME not in await db.ledger_rows()


# ID: 24ac3e23-914b-43c8-88b1-87e30cdce080
async def test_missing_index_converges_but_a_wrong_one_beside_it_still_refuses(
    fresh_database: FreshDatabase,
) -> None:
    """Convergence is only for the authorised shape: a missing index is created
    by the migration (authorised, see the partial-state test above), but the
    same run also finds a same-named index of the wrong shape, which the
    append-only DDL cannot repair — so the whole migration refuses and the
    index it would have created is rolled back with it."""
    db = fresh_database
    await _v2_10_1_shaped(db)
    await db.execute("drop index core.idx_audit_findings_file_run")  # missing
    await db.execute("drop index core.idx_audit_findings_check_run")
    await db.execute(
        "create index idx_audit_findings_check_run "
        "on core.audit_findings using btree (run_id, check_id)"  # wrong order
    )
    with pytest.raises(LedgerEngineError, match="verify probe still fails"):
        await _apply(db, RUN_ID)
    assert (
        await db.scalar(
            "select count(*) from pg_indexes where schemaname='core' "
            "and indexname = 'idx_audit_findings_file_run'"
        )
        == 0
    )  # the creation was rolled back with the refusal
    assert (await _indexdef(db, "idx_audit_findings_check_run")).endswith(
        "(run_id, check_id)"
    )
    assert RUN_ID not in await db.ledger_rows()
