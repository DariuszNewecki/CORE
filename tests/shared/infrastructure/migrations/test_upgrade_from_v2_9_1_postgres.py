# tests/shared/infrastructure/migrations/test_upgrade_from_v2_9_1_postgres.py
"""ADR-162 D1/D3/D4/D9 — the executable v2.9.1 → current upgrade, on a real
PostgreSQL, through the service layer AND through the real ``core-admin`` CLI.

Each test gets its own database on a disposable Postgres container. The
starting states are the released v2.9.1 ``schema.sql`` (committed fixture)
and the current ``schema.sql``; the manifest and migration files are the
real ones.

Proven here:

* fresh install: loading current ``schema.sql`` yields a complete ledger
  (seed == manifest), ``status`` is current, ``migrate --write`` is a no-op,
  and no baseline can be adopted over it;
* the upgrade: a v2.9.1 database has an empty ledger; ``migrate --write``
  refuses and names the remedy; adopting the wrong baseline (v2.10.1) or an
  unknown one refuses without writing; adopting v2.9.1 without ``--write``
  verifies only; with ``--write`` it records exactly the v2.9.1 prefix; then
  ``migrate --write`` executes the whole span (the two ``20260722`` files
  and the ledger column included); ``status`` is current, every
  probe holds, the v2.10.1 fingerprint holds, re-running is a no-op;
* the ``--bootstrap``-after-upgrade trap: a ledger that falsely claims the
  span is reported as a contradiction and ``migrate --write`` refuses;
* ambiguity: a v2.10.1-shaped database with an empty ledger suggests v2.10.1
  and refuses v2.9.1;
* the same sequence driven cold through ``core-admin database ...`` with
  only ``DATABASE_URL`` set, checking exit codes and JSON output.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from shared.infrastructure.repositories.db.common import REPO_ROOT
from shared.infrastructure.repositories.db.ledger_engine import MigrationOutcome
from shared.infrastructure.repositories.db.manifest import load_manifest, parse_manifest
from shared.infrastructure.repositories.db.migration_service import (
    MigrationServiceError,
    adopt_baseline,
    migrate_db,
)
from shared.infrastructure.repositories.db.status_service import status


if TYPE_CHECKING:
    from .conftest import FreshDatabase


pytestmark = [pytest.mark.integration]

assert REPO_ROOT is not None
SCHEMA_SQL = REPO_ROOT / "schema.sql"
SCHEMA_V2_9_1 = REPO_ROOT / "tests" / "fixtures" / "schema" / "schema-v2.9.1.sql"
SCHEMA_V2_10_1 = REPO_ROOT / "tests" / "fixtures" / "schema" / "schema-v2.10.1.sql"
RECONCILED_COLUMN = "20260919_adr162_migrations_reconciled.sql"
BACKFILLS = [
    "20260919b_adr052_core_archive_schema.sql",
    "20260919c_adr054_audit_findings_run_id.sql",
    "20260919d_users_display_name.sql",
    "20260919e_adr052_phase4_drop_runtime_settings.sql",
]


# ── fresh install (D9) ───────────────────────────────────────────────────────


# ID: 75bb4dcb-f084-4ca1-ba9b-a1479c57389b
async def test_fresh_install_from_schema_sql_has_a_complete_ledger(
    fresh_database: FreshDatabase,
) -> None:
    db = fresh_database
    manifest = load_manifest()
    await db.load_schema(SCHEMA_SQL)

    rows = await db.ledger_rows()
    assert list(rows) == list(manifest.order)  # insertion order == manifest order
    assert not any(rows.values())  # seeded, not reconciled

    st = await status(session_factory=db.session_factory)
    assert st.is_current and st.ledger_present and st.schema_present
    assert st.pending_migrations == [] and st.probe_failures == []
    assert st.baseline_suggestion is None

    report = await migrate_db(write=True, session_factory=db.session_factory)
    assert report.pending_before == [] and report.results == []

    # Nothing can be "adopted" over a complete ledger: v2.9.1's and v2.10.1's
    # absence discriminators fail on the current schema (the latter on the
    # ledger column v2.10.2 introduced); v2.10.2 -- the current shape itself --
    # holds but has nothing to record. None of them writes.
    with pytest.raises(MigrationServiceError, match=r"probe \d+/\d+ does not hold"):
        await adopt_baseline("v2.9.1", write=True, session_factory=db.session_factory)
    with pytest.raises(MigrationServiceError, match=r"probe \d+/\d+ does not hold"):
        await adopt_baseline("v2.10.1", write=True, session_factory=db.session_factory)
    noop = await adopt_baseline(
        "v2.10.2", write=True, session_factory=db.session_factory
    )
    assert noop.to_record == [] and noop.recorded == []
    assert list(await db.ledger_rows()) == list(manifest.order)


# ── the upgrade (D1, D3, D4) ─────────────────────────────────────────────────


# ID: dd3afaaf-b648-4038-9853-fd06e7f9bd91
async def test_upgrade_v2_9_1_to_current_end_to_end(
    fresh_database: FreshDatabase,
) -> None:
    db = fresh_database
    manifest = load_manifest()
    v2_9_1_prefix = [
        e.id for e in manifest.entries_through(manifest.baseline("v2.9.1").through)
    ]
    await db.load_schema(SCHEMA_V2_9_1)

    # 1. Inspection: empty ledger on a populated schema, baseline suggested.
    st = await status(session_factory=db.session_factory)
    assert st.ledger_present and st.schema_present
    assert st.applied_migrations == set()
    assert st.pending_migrations == list(manifest.order)
    assert st.baseline_suggestion == "v2.9.1"
    assert not st.is_current

    # 2. --write refuses and names the remedy; nothing written.
    with pytest.raises(MigrationServiceError, match=r"adopt-baseline v2\.9\.1 --write"):
        await migrate_db(write=True, session_factory=db.session_factory)
    assert await db.ledger_rows() == {}

    # 3. Wrong / unknown baselines refuse without writing.
    with pytest.raises(
        MigrationServiceError, match=r"baseline v2\.10\.1 probe \d+/\d+ does not hold"
    ):
        await adopt_baseline("v2.10.1", write=True, session_factory=db.session_factory)
    with pytest.raises(MigrationServiceError, match="not a declared baseline"):
        await adopt_baseline("v9.9.9", write=True, session_factory=db.session_factory)
    assert await db.ledger_rows() == {}

    # 4. Verify-only adoption writes nothing.
    preview = await adopt_baseline(
        "v2.9.1", write=False, session_factory=db.session_factory
    )
    assert preview.to_record == v2_9_1_prefix and preview.recorded == []
    assert await db.ledger_rows() == {}

    # 5. Adoption records exactly the v2.9.1 prefix, nothing beyond.
    adoption = await adopt_baseline(
        "v2.9.1", write=True, session_factory=db.session_factory
    )
    assert adoption.recorded == v2_9_1_prefix
    assert list(await db.ledger_rows()) == v2_9_1_prefix
    span = list(manifest.order[len(v2_9_1_prefix) :])
    st = await status(session_factory=db.session_factory)
    assert st.pending_migrations == span and st.probe_failures == []
    assert st.baseline_suggestion is None  # only offered for an empty ledger

    # 6. Migrate: the whole span executes (the ledger column included —
    #    the engine never adds it out of band).
    report = await migrate_db(write=True, session_factory=db.session_factory)
    assert report.pending_before == span
    assert report.applied == span
    assert report.reconciled == [] and report.markers_backfilled == []
    assert all(
        r.statements_executed > 0
        for r in report.results
        if r.outcome is MigrationOutcome.APPLIED
    )

    # 7. Current: every probe holds, v2.10.1 fingerprint holds, no-op re-run.
    st = await status(session_factory=db.session_factory)
    assert st.is_current and st.pending_migrations == [] and st.probe_failures == []
    assert set(await db.ledger_rows()) == set(manifest.order)
    again = await migrate_db(write=True, session_factory=db.session_factory)
    assert again.pending_before == [] and again.results == []
    with pytest.raises(MigrationServiceError, match=r"probe \d+/\d+ does not hold"):
        await adopt_baseline("v2.9.1", write=True, session_factory=db.session_factory)


# ID: 4e0d61ed-5ef5-4d2f-975c-80e6a6db5b30
async def test_false_ledger_is_a_contradiction_and_write_refuses(
    fresh_database: FreshDatabase,
) -> None:
    """ADR-162 Context, scenario B: `--bootstrap` on the new checkout marked
    all entries applied on a v2.9.1 schema — `status` showed 0 pending while
    the API still failed. Now the contradiction is named and --write refuses."""
    db = fresh_database
    manifest = load_manifest()
    await db.load_schema(SCHEMA_V2_9_1)
    for mig in manifest.order:
        await db.execute(f"insert into core._migrations (id) values ('{mig}')")

    st = await status(session_factory=db.session_factory)
    assert st.pending_migrations == []
    assert (
        "20260712_adr148_finalizing_and_consequence_recorded_at.sql"
        in st.probe_failures
    )
    assert "20260830_821_create_task_assignee_roles.sql" in st.probe_failures
    assert not st.is_current

    with pytest.raises(MigrationServiceError, match="contradiction"):
        await migrate_db(write=True, session_factory=db.session_factory)


# ID: 7da1b9ae-5435-459a-ba18-6fe71f27633a
async def test_v2_10_1_shaped_database_refuses_v2_9_1_and_suggests_v2_10_1(
    fresh_database: FreshDatabase,
) -> None:
    db = fresh_database
    manifest = load_manifest()
    # The committed v2.10.1 release schema: an install whose ledger was never
    # seeded (v2.10.1 shipped no seed). A full replay would not do here since
    # v2.10.2 declared a baseline: replaying to current adds the ledger
    # column, and that shape is v2.10.2's, not v2.10.1's.
    await db.load_schema(SCHEMA_V2_10_1)

    st = await status(session_factory=db.session_factory)
    assert st.baseline_suggestion == "v2.10.1"

    # v2.9.1 carries absence discriminators, so it is refused on its own
    # probes; the later-baseline guard is exercised separately below.
    with pytest.raises(MigrationServiceError, match=r"probe \d+/\d+ does not hold"):
        await adopt_baseline("v2.9.1", write=True, session_factory=db.session_factory)
    assert await db.ledger_rows() == {}

    adoption = await adopt_baseline(
        "v2.10.1", write=True, session_factory=db.session_factory
    )
    assert adoption.through == manifest.baseline("v2.10.1").through
    assert adoption.recorded == [
        e.id for e in manifest.entries_through(manifest.baseline("v2.10.1").through)
    ]
    report = await migrate_db(write=True, session_factory=db.session_factory)
    assert report.pending_before == [RECONCILED_COLUMN, *BACKFILLS]
    assert report.applied == [RECONCILED_COLUMN]  # idempotent ADD COLUMN IF NOT EXISTS
    assert report.reconciled == BACKFILLS  # structures already present: no DDL re-run
    assert (await status(session_factory=db.session_factory)).is_current


# ID: de71a6c2-2435-4f2d-95af-22c54cc9bac1
async def test_adopting_an_earlier_baseline_when_a_later_one_holds_is_refused(
    fresh_database: FreshDatabase, tmp_path: Path
) -> None:
    """The later-baseline guard, with a synthetic manifest whose earlier
    baseline has no absence discriminator: both fingerprints hold, so
    adopting the earlier one would leave present changes pending."""
    db = fresh_database
    await db.execute("create schema core")
    await db.execute("create table core.a (x int)")
    await db.execute("create table core.b (x int)")
    for name in ("001_a.sql", "002_b.sql"):
        (tmp_path / name).write_text("select 1;", encoding="utf-8")
    manifest = parse_manifest(
        {
            "migrations": {
                "directory": str(tmp_path),
                "order": ["001_a.sql", "002_b.sql"],
                "baselines": {
                    "v1": {
                        "through": "001_a.sql",
                        "probes": ["select to_regclass('core.a') is not null"],
                    },
                    "v2": {
                        "through": "002_b.sql",
                        "probes": ["select to_regclass('core.b') is not null"],
                    },
                },
            }
        }
    )
    with pytest.raises(MigrationServiceError, match="later baseline v2"):
        await adopt_baseline(
            "v1", write=True, session_factory=db.session_factory, manifest=manifest
        )
    assert await db.ledger_rows() == {}
    adoption = await adopt_baseline(
        "v2", write=True, session_factory=db.session_factory, manifest=manifest
    )
    assert adoption.recorded == ["001_a.sql", "002_b.sql"]


# ── the same sequence through the real CLI entry point ──────────────────────


def _core_admin(database_url: str, *args: str) -> tuple[int, str, str]:
    exe = Path(sys.executable).parent / "core-admin"
    if not exe.is_file():
        pytest.skip("core-admin entry point not installed next to the interpreter")
    env = {
        **{k: v for k, v in os.environ.items() if k not in {"DATABASE_URL"}},
        "DATABASE_URL": database_url,
        "PYTEST_CURRENT_TEST": "",  # not a pytest process: settings use .env + env
    }
    env.pop("PYTEST_CURRENT_TEST")
    proc = subprocess.run(
        [str(exe), "database", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
        timeout=180,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


# ID: f4467513-ce95-4954-9e76-b27cf1d8ed5f
async def test_cli_upgrade_sequence_cold(fresh_database: FreshDatabase) -> None:
    db = fresh_database
    manifest = load_manifest()
    await db.load_schema(SCHEMA_V2_9_1)
    url = db.url

    code, out, _ = _core_admin(url, "status", "--format", "json")
    assert code == 2, out[-800:]
    payload = json.loads(out[out.index("{") :])
    assert payload["baseline_suggestion"] == "v2.9.1" and payload["current"] is False

    code, out, _ = _core_admin(url, "migrate", "--write")
    assert code == 1 and "adopt-baseline v2.9.1 --write" in out
    assert await db.ledger_rows() == {}

    code, out, _ = _core_admin(url, "migrate", "--adopt-baseline", "v2.10.1", "--write")
    assert code == 1 and "does not hold" in out
    assert await db.ledger_rows() == {}

    code, out, _ = _core_admin(url, "migrate", "--adopt-baseline", "v2.9.1")
    assert code == 0 and "DRY RUN" in out and "would be recorded" in out
    assert await db.ledger_rows() == {}

    code, out, _ = _core_admin(url, "migrate", "--adopt-baseline", "v2.9.1", "--write")
    assert code == 0 and "adopted" in out, out[-800:]

    code, out, _ = _core_admin(url, "migrate")
    assert code == 0 and "Dry run" in out and RECONCILED_COLUMN in out

    code, out, _ = _core_admin(url, "migrate", "--write")
    assert code == 0 and "Migrations complete" in out, out[-800:]
    assert "14 applied, 0 reconciled" in out  # the whole span incl. U5a backfills

    code, out, _ = _core_admin(url, "status", "--format", "json")
    assert code == 0, out[-800:]
    payload = json.loads(out[out.index("{") :])
    assert payload["current"] is True and payload["pending_migrations"] == []
    assert sorted(payload["applied_migrations"]) == sorted(manifest.order)
