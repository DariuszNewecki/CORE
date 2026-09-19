# tests/shared/infrastructure/migrations/test_ledger_engine_postgres.py
"""ADR-162 D7 (R7-A) — the atomic ledger engine against a real PostgreSQL.

Every test runs the *real* engine (``ledger_engine`` / ``migration_service``)
with a synthetic manifest and SQL files in a temporary directory, against a
database created for that test alone on a disposable Postgres container.
Proven here:

* rollback — a failing migration leaves neither its changes nor its ledger row;
* retry — after the file is fixed, the same migration applies cleanly;
* ordering — a failure at N leaves 1..N-1 recorded and N.. pending;
* concurrency — two concurrent appliers of the same pending migration apply it
  exactly once (advisory lock + re-read inside the lock);
* reconciliation — a ``reconcilable`` entry whose probe already holds is
  recorded with ``reconciled = true`` and executes zero statements; the same
  entry on a database where the probe fails is executed;
* verify-after-execute — a migration whose probe still fails after running is
  rolled back and not recorded;
* refusals — ``transactional: false`` and foreign transaction control are
  refused before anything runs;
* one schema authority — ``ensure_ledger`` creates a missing ledger in its
  legacy shape and never alters an existing one; rows are legacy-shaped
  until the column migration runs, and a reconciled row's marker is set
  afterwards by an explicit backfill;
* read-only inspection — status/get_applied never create the ledger table.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from shared.infrastructure.repositories.db import migration_service
from shared.infrastructure.repositories.db.ledger_engine import (
    LedgerEngineError,
    MigrationOutcome,
    apply_migration,
    backfill_reconciled_markers,
    ensure_ledger,
    get_applied,
)
from shared.infrastructure.repositories.db.manifest import (
    Manifest,
    MigrationEntry,
    parse_manifest,
)
from shared.infrastructure.repositories.db.migration_service import (
    MigrationServiceError,
    migrate_db,
)
from shared.infrastructure.repositories.db.status_service import status


if TYPE_CHECKING:
    from .conftest import FreshDatabase


pytestmark = [pytest.mark.integration]


# ── helpers ──────────────────────────────────────────────────────────────────


def _write(migrations_dir: Path, name: str, sql: str) -> Path:
    path = migrations_dir / name
    path.write_text(sql, encoding="utf-8")
    return path


def _manifest(
    migrations_dir: Path, order: list[str], probes: dict | None = None
) -> Manifest:
    """A synthetic manifest whose ``directory`` is absolute (repo_root '/')."""
    return parse_manifest(
        {
            "migrations": {
                "directory": str(migrations_dir),
                "order": order,
                **({"probes": probes} if probes else {}),
            }
        }
    )


async def _apply(
    db: FreshDatabase, manifest: Manifest, mig_id: str
) -> MigrationOutcome:
    result = await apply_migration(
        manifest.entry(mig_id),
        manifest.sql_path(mig_id, Path("/")),
        session_factory=db.session_factory,
    )
    return result.outcome


TABLE_EXISTS = "select to_regclass('core.{t}') is not null"
RECONCILED_COLUMN_DDL = (
    "alter table core._migrations add column reconciled boolean not null default false"
)


async def _modern_ledger(db: FreshDatabase) -> None:
    """A ledger that has taken 20260919_adr162_migrations_reconciled.sql."""
    await ensure_ledger(db.session_factory)
    await db.execute(RECONCILED_COLUMN_DDL)


# ── atomicity ────────────────────────────────────────────────────────────────


# ID: d5f6324e-4d47-4040-a0ca-4a2a3090b1ed
async def test_failed_migration_leaves_no_change_and_no_ledger_row(
    fresh_database: FreshDatabase, tmp_path: Path
) -> None:
    db = fresh_database
    await ensure_ledger(db.session_factory)
    _write(
        tmp_path,
        "001_bad.sql",
        "BEGIN;\nCREATE TABLE core.t_bad (x int);\n"
        "INSERT INTO core.t_bad VALUES (1);\n"
        "SELECT 1/0;\nCOMMIT;\n",
    )
    manifest = _manifest(tmp_path, ["001_bad.sql"])

    with pytest.raises(Exception):
        await _apply(db, manifest, "001_bad.sql")

    assert await db.scalar(TABLE_EXISTS.format(t="t_bad")) is False
    assert await db.ledger_rows() == {}


# ID: 8e260305-36cc-4862-84a3-fcb866c2c882
async def test_retry_after_fix_applies_and_records(
    fresh_database: FreshDatabase, tmp_path: Path
) -> None:
    db = fresh_database
    await ensure_ledger(db.session_factory)
    path = _write(
        tmp_path,
        "001_t.sql",
        "BEGIN;\nCREATE TABLE core.t_retry (x int);\nSELECT 1/0;\nCOMMIT;\n",
    )
    manifest = _manifest(tmp_path, ["001_t.sql"])
    with pytest.raises(Exception):
        await _apply(db, manifest, "001_t.sql")
    assert await db.ledger_rows() == {}

    path.write_text(
        "BEGIN;\nCREATE TABLE core.t_retry (x int);\nCOMMIT;\n", encoding="utf-8"
    )
    assert await _apply(db, manifest, "001_t.sql") is MigrationOutcome.APPLIED
    assert await db.scalar(TABLE_EXISTS.format(t="t_retry")) is True
    assert await db.ledger_rows() == {"001_t.sql": False}


# ID: 9a187ccd-1acd-4be5-bc5a-498e1e7f5d9d
async def test_migrate_db_stops_at_first_failure_keeping_earlier_ones(
    fresh_database: FreshDatabase, tmp_path: Path
) -> None:
    db = fresh_database
    _write(tmp_path, "001_a.sql", "CREATE TABLE core.t_a (x int);")
    _write(tmp_path, "002_b.sql", "CREATE TABLE core.t_b (x int);\nSELECT 1/0;")
    _write(tmp_path, "003_c.sql", "CREATE TABLE core.t_c (x int);")
    manifest = _manifest(tmp_path, ["001_a.sql", "002_b.sql", "003_c.sql"])

    with pytest.raises(MigrationServiceError) as excinfo:
        await migrate_db(
            write=True, session_factory=db.session_factory, manifest=manifest
        )
    assert "002_b.sql" in str(excinfo.value)
    assert "not recorded" in str(excinfo.value)

    assert await db.ledger_rows() == {"001_a.sql": False}
    assert await db.scalar(TABLE_EXISTS.format(t="t_a")) is True
    assert await db.scalar(TABLE_EXISTS.format(t="t_b")) is False
    assert await db.scalar(TABLE_EXISTS.format(t="t_c")) is False

    # Re-running after the fix picks up exactly where it stopped.
    _write(tmp_path, "002_b.sql", "CREATE TABLE core.t_b (x int);")
    report = await migrate_db(
        write=True, session_factory=db.session_factory, manifest=manifest
    )
    assert report.pending_before == ["002_b.sql", "003_c.sql"]
    assert report.applied == ["002_b.sql", "003_c.sql"]
    assert set(await db.ledger_rows()) == {"001_a.sql", "002_b.sql", "003_c.sql"}

    # And once more is a no-op.
    report = await migrate_db(
        write=True, session_factory=db.session_factory, manifest=manifest
    )
    assert report.pending_before == [] and report.results == []


# ── concurrency ──────────────────────────────────────────────────────────────


# ID: 2d71c0a8-68d9-4592-9fff-a52b005b29e0
async def test_concurrent_appliers_apply_exactly_once(
    fresh_database: FreshDatabase, tmp_path: Path
) -> None:
    """Two writers race on the same pending migration; the advisory lock
    serialises them and the loser sees the row inside the lock and skips.
    The migration is NOT idempotent (plain CREATE TABLE + INSERT), so a
    double application would have failed loudly."""
    db = fresh_database
    await ensure_ledger(db.session_factory)
    _write(
        tmp_path,
        "001_race.sql",
        "CREATE TABLE core.t_race (x int);\nINSERT INTO core.t_race VALUES (1);\n"
        "SELECT pg_sleep(0.5);",
    )
    manifest = _manifest(tmp_path, ["001_race.sql"])

    outcomes = await asyncio.gather(
        _apply(db, manifest, "001_race.sql"),
        _apply(db, manifest, "001_race.sql"),
        _apply(db, manifest, "001_race.sql"),
    )
    assert sorted(o.value for o in outcomes) == [
        "applied",
        "skipped_recorded",
        "skipped_recorded",
    ]
    assert await db.scalar("select count(*) from core.t_race") == 1
    assert await db.ledger_rows() == {"001_race.sql": False}


# ── reconciliation (D12 §2) ──────────────────────────────────────────────────


PROBE_T_REC = "select to_regclass('core.t_rec') is not null"


# ID: c1d2a3a1-0250-4fcd-aae3-8410479957de
async def test_reconcilable_entry_with_true_probe_is_recorded_without_execution(
    fresh_database: FreshDatabase, tmp_path: Path
) -> None:
    db = fresh_database
    await _modern_ledger(db)
    # The change is already present (applied "by hand"); the file would blow
    # up if executed, which is how we know it was not.
    await db.execute("CREATE TABLE core.t_rec (x int)")
    _write(tmp_path, "001_rec.sql", "CREATE TABLE core.t_rec (x int);")
    manifest = _manifest(
        tmp_path,
        ["001_rec.sql"],
        {"001_rec.sql": {"verify": PROBE_T_REC, "reconcilable": True}},
    )
    result = await apply_migration(
        manifest.entry("001_rec.sql"),
        manifest.sql_path("001_rec.sql", Path("/")),
        session_factory=db.session_factory,
    )
    assert result.outcome is MigrationOutcome.RECONCILED
    assert result.statements_executed == 0
    assert result.marker_recorded is True
    assert await db.ledger_rows() == {"001_rec.sql": True}


# ID: 06fa9c25-1bcc-4eb7-aacc-f193fe509fdd
async def test_reconciled_row_on_a_legacy_ledger_gets_its_marker_by_backfill(
    fresh_database: FreshDatabase, tmp_path: Path
) -> None:
    """Before 20260919_adr162_migrations_reconciled.sql has run the ledger has
    no ``reconciled`` column: the row is recorded legacy-shaped (nothing
    executed), the result says the marker is missing, and the explicit
    backfill sets it once the column exists — never by altering the table
    behind the migration's back."""
    db = fresh_database
    await ensure_ledger(db.session_factory)  # legacy shape only
    await db.execute("CREATE TABLE core.t_rec (x int)")
    _write(tmp_path, "001_rec.sql", "CREATE TABLE core.t_rec (x int);")
    manifest = _manifest(
        tmp_path,
        ["001_rec.sql"],
        {"001_rec.sql": {"verify": PROBE_T_REC, "reconcilable": True}},
    )
    result = await apply_migration(
        manifest.entry("001_rec.sql"),
        manifest.sql_path("001_rec.sql", Path("/")),
        session_factory=db.session_factory,
    )
    assert result.outcome is MigrationOutcome.RECONCILED
    assert result.marker_recorded is False
    assert await db.ledger_rows() == {"001_rec.sql": False}
    assert (
        await db.scalar(
            "select exists (select 1 from information_schema.columns where "
            "table_schema='core' and table_name='_migrations' and column_name='reconciled')"
        )
        is False
    ), "the engine must not add the column itself"

    # Column still absent: backfill is a no-op.
    assert (
        await backfill_reconciled_markers(
            ["001_rec.sql"], session_factory=db.session_factory
        )
        == []
    )
    # The ledgered migration adds the column; then the marker can be set.
    await db.execute(RECONCILED_COLUMN_DDL)
    assert await backfill_reconciled_markers(
        ["001_rec.sql"], session_factory=db.session_factory
    ) == ["001_rec.sql"]
    assert await db.ledger_rows() == {"001_rec.sql": True}
    assert (
        await backfill_reconciled_markers(
            ["001_rec.sql"], session_factory=db.session_factory
        )
        == []
    )


# ID: b909a362-5438-477b-b0f8-b30d1e937986
async def test_reconcilable_entry_with_false_probe_is_executed(
    fresh_database: FreshDatabase, tmp_path: Path
) -> None:
    db = fresh_database
    await ensure_ledger(db.session_factory)
    _write(tmp_path, "001_rec.sql", "CREATE TABLE core.t_rec (x int);")
    manifest = _manifest(
        tmp_path,
        ["001_rec.sql"],
        {"001_rec.sql": {"verify": PROBE_T_REC, "reconcilable": True}},
    )
    result = await apply_migration(
        manifest.entry("001_rec.sql"),
        manifest.sql_path("001_rec.sql", Path("/")),
        session_factory=db.session_factory,
    )
    assert result.outcome is MigrationOutcome.APPLIED
    assert result.statements_executed == 1
    assert await db.scalar(PROBE_T_REC) is True
    assert await db.ledger_rows() == {"001_rec.sql": False}


# ID: 99d85c06-2735-4cff-9a74-c735d9b5b13d
async def test_non_reconcilable_entry_is_executed_even_when_probe_holds(
    fresh_database: FreshDatabase, tmp_path: Path
) -> None:
    """Reconcile-by-probe is not a default (D12 §2): without the marker the
    engine executes, and a non-idempotent file on an already-migrated schema
    fails loudly and records nothing — the operator's remedy is baseline
    adoption, not silent reconciliation."""
    db = fresh_database
    await ensure_ledger(db.session_factory)
    await db.execute("CREATE TABLE core.t_rec (x int)")
    _write(tmp_path, "001_rec.sql", "CREATE TABLE core.t_rec (x int);")
    manifest = _manifest(
        tmp_path, ["001_rec.sql"], {"001_rec.sql": {"verify": PROBE_T_REC}}
    )
    with pytest.raises(Exception):
        await _apply(db, manifest, "001_rec.sql")
    assert await db.ledger_rows() == {}


# ID: 9ebce084-bf94-48f1-812e-322c84da794b
async def test_verify_probe_failing_after_execution_rolls_back(
    fresh_database: FreshDatabase, tmp_path: Path
) -> None:
    db = fresh_database
    await ensure_ledger(db.session_factory)
    _write(tmp_path, "001_x.sql", "CREATE TABLE core.t_x (x int);")
    manifest = _manifest(
        tmp_path,
        ["001_x.sql"],
        {"001_x.sql": {"verify": "select to_regclass('core.t_other') is not null"}},
    )
    with pytest.raises(LedgerEngineError, match="still fails after execution"):
        await _apply(db, manifest, "001_x.sql")
    assert await db.scalar(TABLE_EXISTS.format(t="t_x")) is False
    assert await db.ledger_rows() == {}


# ── refusals (fail closed) ───────────────────────────────────────────────────


# ID: 227138fe-a270-4403-baed-fa123efa1686
async def test_non_transactional_flag_is_refused_before_anything_runs(
    fresh_database: FreshDatabase, tmp_path: Path
) -> None:
    db = fresh_database
    await ensure_ledger(db.session_factory)
    path = _write(tmp_path, "001_nt.sql", "CREATE TABLE core.t_nt (x int);")
    entry = MigrationEntry(id="001_nt.sql", transactional=False)
    with pytest.raises(LedgerEngineError, match="transactional: false"):
        await apply_migration(entry, path, session_factory=db.session_factory)
    assert await db.scalar(TABLE_EXISTS.format(t="t_nt")) is False
    assert await db.ledger_rows() == {}


# ID: 89aa02bf-4504-447d-be86-16abd8b955d1
async def test_foreign_transaction_control_is_refused_before_anything_runs(
    fresh_database: FreshDatabase, tmp_path: Path
) -> None:
    db = fresh_database
    await ensure_ledger(db.session_factory)
    path = _write(
        tmp_path,
        "001_tc.sql",
        "CREATE TABLE core.t_tc (x int);\nCOMMIT;\nCREATE TABLE core.t_tc2 (x int);",
    )
    with pytest.raises(LedgerEngineError, match="transaction control"):
        await apply_migration(
            MigrationEntry(id="001_tc.sql"), path, session_factory=db.session_factory
        )
    assert await db.scalar(TABLE_EXISTS.format(t="t_tc")) is False
    assert await db.ledger_rows() == {}


# ID: 2751b7a5-4ae7-4902-9830-679dce6fbeab
async def test_leading_begin_and_trailing_commit_are_stripped_and_atomic(
    fresh_database: FreshDatabase, tmp_path: Path
) -> None:
    """With the in-file COMMIT kept, the DDL would commit before the failing
    statement (the pre-ADR-162 defect); stripped, everything rolls back."""
    db = fresh_database
    await ensure_ledger(db.session_factory)
    _write(
        tmp_path,
        "001_bc.sql",
        "BEGIN;\nCREATE TABLE core.t_bc (x int);\nCOMMIT;\n",
    )
    # A second file proves the statement after the stripped COMMIT position
    # is inside the same transaction as the DDL.
    _write(
        tmp_path,
        "002_bc.sql",
        "BEGIN;\nCREATE TABLE core.t_bc2 (x int);\nSELECT 1/0;\nCOMMIT;\n",
    )
    manifest = _manifest(tmp_path, ["001_bc.sql", "002_bc.sql"])
    assert await _apply(db, manifest, "001_bc.sql") is MigrationOutcome.APPLIED
    with pytest.raises(Exception):
        await _apply(db, manifest, "002_bc.sql")
    assert await db.scalar(TABLE_EXISTS.format(t="t_bc")) is True
    assert await db.scalar(TABLE_EXISTS.format(t="t_bc2")) is False
    assert await db.ledger_rows() == {"001_bc.sql": False}


# ── ledger structure & read-only inspection ──────────────────────────────────


# ID: 509c6514-b5f3-4ccc-816d-3aff25883616
async def test_ensure_ledger_creates_legacy_shape_and_never_alters_an_existing_ledger(
    fresh_database: FreshDatabase,
) -> None:
    db = fresh_database
    columns_sql = (
        "select array_agg(column_name::text order by ordinal_position) "
        "from information_schema.columns where table_schema='core' "
        "and table_name='_migrations'"
    )
    # Absent ledger: created in the legacy shape only.
    await ensure_ledger(db.session_factory)
    assert await db.scalar(columns_sql) == ["id", "applied_at"]
    # Existing legacy ledger with a historical row: untouched, idempotent.
    await db.execute("INSERT INTO core._migrations (id) VALUES ('legacy.sql')")
    await ensure_ledger(db.session_factory)
    assert await db.scalar(columns_sql) == ["id", "applied_at"]
    assert await db.ledger_rows() == {"legacy.sql": False}


# ID: 0ae37df0-7053-47a5-9632-030e9977a9e9
async def test_inspection_never_creates_the_ledger(
    fresh_database: FreshDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = fresh_database
    _write(tmp_path, "001_a.sql", "CREATE TABLE core.t_a (x int);")
    manifest = _manifest(tmp_path, ["001_a.sql"])

    assert await get_applied(db.session_factory) == set()
    report = await migrate_db(
        write=False, session_factory=db.session_factory, manifest=manifest
    )
    assert report.pending_before == ["001_a.sql"] and report.results == []

    monkeypatch.setattr(migration_service, "load_manifest", lambda **_: manifest)
    monkeypatch.setattr(
        "shared.infrastructure.repositories.db.status_service.load_manifest",
        lambda **_: manifest,
    )
    st = await status(session_factory=db.session_factory)
    assert st.is_connected is True
    assert st.ledger_present is False
    assert st.pending_migrations == ["001_a.sql"]

    assert await db.scalar("select to_regclass('core._migrations') is null") is True
    assert await db.scalar("select to_regclass('core.t_a') is null") is True
