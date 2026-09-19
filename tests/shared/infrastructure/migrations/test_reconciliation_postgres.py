# tests/shared/infrastructure/migrations/test_reconciliation_postgres.py
"""ADR-162 D6 / D12 §2 — reconcile-by-probe on a real v2.9.1 database.

Starting point for every test: the released v2.9.1 ``schema.sql`` (committed
fixture, byte-identical to the tag) loaded into a database created for that
test alone, with the ledger seeded through the v2.9.1 baseline the way
verified adoption records it (engine primitive; the CLI command is U4).

Proven here, with the REAL manifest and the REAL migration files:

* the live-database case — both ``20260722_active_finding_*`` files applied
  by hand (per their ROLLOUT runbook) before the manifest knew them — is
  recorded as ``reconciled`` by ``--write`` with ZERO statements executed;
* the unapplied case executes the same two files;
* everything else in the span is executed, the ledger's own column entry is
  reconciled (the engine created it first), and afterwards every per-entry
  probe holds, the v2.10.1 baseline fingerprint holds and nothing is pending;
* baseline probes discriminate: v2.9.1 holds and v2.10.1 does not on a
  v2.9.1 database, and the reverse after the upgrade.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from shared.infrastructure.repositories.db.common import REPO_ROOT
from shared.infrastructure.repositories.db.ledger_engine import (
    MigrationOutcome,
    ensure_ledger,
    record_ledger_row,
    run_probe,
)
from shared.infrastructure.repositories.db.manifest import Manifest, load_manifest
from shared.infrastructure.repositories.db.migration_service import migrate_db


if TYPE_CHECKING:
    from .conftest import FreshDatabase


pytestmark = [pytest.mark.integration]

assert REPO_ROOT is not None
SCHEMA_V2_9_1 = REPO_ROOT / "tests" / "fixtures" / "schema" / "schema-v2.9.1.sql"

DEDUP = "20260722_active_finding_dedup.sql"
RECONCILE = "20260722_active_finding_reconcile.sql"
RECONCILED_COLUMN = "20260919_adr162_migrations_reconciled.sql"


async def _baseline_holds(db: FreshDatabase, manifest: Manifest, tag: str) -> bool:
    async with db.session_factory() as session:
        return all([await run_probe(session, q) for q in manifest.baseline(tag).probes])


async def _entry_probe(db: FreshDatabase, manifest: Manifest, mig_id: str) -> bool:
    verify = manifest.entry(mig_id).verify
    assert verify is not None
    async with db.session_factory() as session:
        return await run_probe(session, verify)


async def _v2_9_1_database(db: FreshDatabase, manifest: Manifest) -> None:
    """Load the released v2.9.1 schema and seed the ledger through its baseline."""
    await db.load_schema(SCHEMA_V2_9_1)
    await ensure_ledger(db.session_factory)
    for entry in manifest.entries_through(manifest.baseline("v2.9.1").through):
        assert await record_ledger_row(
            entry.id, reconciled=False, session_factory=db.session_factory
        )


async def _apply_by_hand(db: FreshDatabase, manifest: Manifest, mig_id: str) -> None:
    """What the ROLLOUT runbook did on the live database: ``psql -f <file>``."""
    await db.execute_script(
        manifest.sql_path(mig_id, REPO_ROOT).read_text(encoding="utf-8")
    )


# ID: b11be876-a47b-45ba-a7dd-9a7183fae95b
async def test_v2_9_1_fixture_is_the_v2_9_1_baseline_and_not_v2_10_1(
    fresh_database: FreshDatabase,
) -> None:
    db = fresh_database
    manifest = load_manifest()
    await _v2_9_1_database(db, manifest)
    assert await _baseline_holds(db, manifest, "v2.9.1") is True
    assert await _baseline_holds(db, manifest, "v2.10.1") is False
    report = await migrate_db(write=False, session_factory=db.session_factory)
    assert report.pending_before == list(
        manifest.order[manifest.order.index(manifest.baseline("v2.9.1").through) + 1 :]
    )


# ID: f21711a1-5eba-4cae-9e9c-74754f3af342
async def test_hand_applied_20260722_state_is_reconciled_without_rerunning_sql(
    fresh_database: FreshDatabase,
) -> None:
    db = fresh_database
    manifest = load_manifest()
    await _v2_9_1_database(db, manifest)
    await _apply_by_hand(db, manifest, DEDUP)
    await _apply_by_hand(db, manifest, RECONCILE)
    assert await _entry_probe(db, manifest, DEDUP) is True
    assert await _entry_probe(db, manifest, RECONCILE) is True

    report = await migrate_db(write=True, session_factory=db.session_factory)

    by_id = {r.id: r for r in report.results}
    for mig_id in (DEDUP, RECONCILE):
        assert by_id[mig_id].outcome is MigrationOutcome.RECONCILED, mig_id
        assert by_id[mig_id].statements_executed == 0, mig_id
    assert by_id[RECONCILED_COLUMN].outcome is MigrationOutcome.RECONCILED
    executed = [r.id for r in report.results if r.outcome is MigrationOutcome.APPLIED]
    assert executed == [
        m
        for m in report.pending_before
        if m not in (DEDUP, RECONCILE, RECONCILED_COLUMN)
    ]
    assert all(r.statements_executed > 0 for r in report.results if r.id in executed)

    rows = await db.ledger_rows()
    assert set(rows) == set(manifest.order)
    assert {k for k, v in rows.items() if v} == {DEDUP, RECONCILE, RECONCILED_COLUMN}
    await _assert_current(db, manifest)


# ID: fe05ad23-2146-40e7-af7e-4de9f5f72aea
async def test_unapplied_20260722_state_executes_the_files(
    fresh_database: FreshDatabase,
) -> None:
    db = fresh_database
    manifest = load_manifest()
    await _v2_9_1_database(db, manifest)
    assert await _entry_probe(db, manifest, DEDUP) is False
    assert await _entry_probe(db, manifest, RECONCILE) is False

    report = await migrate_db(write=True, session_factory=db.session_factory)

    by_id = {r.id: r for r in report.results}
    for mig_id in (DEDUP, RECONCILE):
        assert by_id[mig_id].outcome is MigrationOutcome.APPLIED, mig_id
        assert by_id[mig_id].statements_executed > 0, mig_id
    rows = await db.ledger_rows()
    assert set(rows) == set(manifest.order)
    assert {k for k, v in rows.items() if v} == {RECONCILED_COLUMN}
    await _assert_current(db, manifest)


async def _assert_current(db: FreshDatabase, manifest: Manifest) -> None:
    for entry in manifest.entries:
        if entry.verify:
            assert await _entry_probe(db, manifest, entry.id) is True, entry.id
    assert await _baseline_holds(db, manifest, "v2.10.1") is True
    assert await _baseline_holds(db, manifest, "v2.9.1") is False
    again = await migrate_db(write=True, session_factory=db.session_factory)
    assert again.pending_before == [] and again.results == []


# ID: 3a6ef647-b4c6-484a-a282-301622acf19d
async def test_reconciliation_requires_the_complete_postcondition(
    fresh_database: FreshDatabase,
) -> None:
    """Columns present but a row violating the data postcondition: the
    reconcile probe is false, so the engine executes the file instead of
    recording it (D12 §2 — the probe must prove the COMPLETE postcondition)."""
    db = fresh_database
    manifest = load_manifest()
    await _v2_9_1_database(db, manifest)
    await _apply_by_hand(db, manifest, DEDUP)
    # Two active findings with the same identity: reconcile's data
    # postcondition (no duplicate active identity) does not hold.
    await db.execute(
        "insert into core.worker_registry (worker_uuid, worker_name, worker_class, phase) "
        "values ('00000000-0000-4000-8000-000000000001', 't', 'T', 'audit')"
    )
    await db.execute(
        "insert into core.blackboard_entries "
        "(worker_uuid, entry_type, phase, subject, status, resolution_mechanism) values "
        "('00000000-0000-4000-8000-000000000001', 'finding', 'audit', 'dup.subject', 'open', 'human'), "
        "('00000000-0000-4000-8000-000000000001', 'finding', 'audit', 'dup.subject', 'open', 'human')"
    )
    assert await _entry_probe(db, manifest, DEDUP) is True
    assert await _entry_probe(db, manifest, RECONCILE) is False

    report = await migrate_db(write=True, session_factory=db.session_factory)
    by_id = {r.id: r for r in report.results}
    assert by_id[DEDUP].outcome is MigrationOutcome.RECONCILED
    assert by_id[RECONCILE].outcome is MigrationOutcome.APPLIED
    # The executed reconciliation collapsed the duplicates and the index holds.
    assert await _entry_probe(db, manifest, RECONCILE) is True
    assert (
        await db.scalar(
            "select count(*) from core.blackboard_entries "
            "where subject = 'dup.subject' and status = 'open'"
        )
        == 1
    )
