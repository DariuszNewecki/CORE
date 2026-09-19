"""Migration ledger — hermetic tests for the manifest + service layer.

Covers:
  - Manifest loads and contains expected structure
  - All listed SQL files exist on disk
  - Order list is sorted (date-prefixed names enforce chronological order)
  - load_policy() returns the manifest dict
  - migrate_db(write=False) is a pure dry run: no ledger creation, no apply
  - migrate_db(write=True) applies pending entries in manifest order and
    stops at the first failure
  - bootstrap_migrations() records only un-applied entries without running SQL

DB-backed proofs of atomicity, retry and concurrency live in
``tests/shared/infrastructure/migrations/`` (integration, disposable Postgres).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import yaml

from shared.infrastructure.repositories.db.common import REPO_ROOT, load_policy
from shared.infrastructure.repositories.db.ledger_engine import (
    MigrationOutcome,
    MigrationResult,
)
from shared.infrastructure.repositories.db.migration_service import (
    MigrationServiceError,
    bootstrap_migrations,
    migrate_db,
)


assert REPO_ROOT is not None
_MANIFEST = REPO_ROOT / "infra" / "migrations" / "manifest.yaml"
_MIGRATIONS_DIR = REPO_ROOT / "infra" / "scripts" / "migrations"
_SVC = "shared.infrastructure.repositories.db.migration_service"


# ---------------------------------------------------------------------------
# Manifest structure
# ---------------------------------------------------------------------------


# ID: c2a93cab-fa6b-47cd-ad40-643ee457b7f2
def test_manifest_exists() -> None:
    """infra/migrations/manifest.yaml must be present."""
    assert _MANIFEST.exists(), f"manifest not found at {_MANIFEST}"


# ID: 8a72547a-eb93-4ed0-860a-a7960eeede41
def test_manifest_has_required_keys() -> None:
    """Manifest must have migrations.directory and migrations.order."""
    data = yaml.safe_load(_MANIFEST.read_text(encoding="utf-8"))
    cfg = data.get("migrations", {})
    assert "directory" in cfg, "manifest missing migrations.directory"
    assert "order" in cfg, "manifest missing migrations.order"
    assert isinstance(cfg["order"], list), "migrations.order must be a list"
    assert len(cfg["order"]) > 0, "migrations.order must not be empty"


# ID: f2438922-ed74-45f9-9e12-a9d80a5a73bf
def test_all_manifest_sql_files_exist() -> None:
    """Every entry in migrations.order must have a corresponding .sql file on disk."""
    cfg = yaml.safe_load(_MANIFEST.read_text(encoding="utf-8"))["migrations"]
    missing = [f for f in cfg["order"] if not (_MIGRATIONS_DIR / f).exists()]
    assert not missing, f"Missing SQL files: {missing}"


# ID: daf33d4b-4885-4034-9322-e7ecdcad1ee4
def test_manifest_order_is_sorted() -> None:
    """Date-prefixed filenames must appear in ascending order (chronological)."""
    cfg = yaml.safe_load(_MANIFEST.read_text(encoding="utf-8"))["migrations"]
    order = cfg["order"]
    assert order == sorted(order), (
        "migrations.order is not sorted — new entries must be appended, not inserted"
    )


# ---------------------------------------------------------------------------
# load_policy()
# ---------------------------------------------------------------------------


# ID: 8b98d6f7-22ad-4063-91ef-ad72aa43c4fc
def test_load_policy_returns_manifest_dict() -> None:
    """load_policy() must return a dict with a migrations key."""
    pol = load_policy()
    assert isinstance(pol, dict)
    assert "migrations" in pol
    assert "order" in pol["migrations"]


# ---------------------------------------------------------------------------
# migrate_db() — orchestration with the engine mocked out
# ---------------------------------------------------------------------------


# ID: a473cdc3-8b5d-4fbf-ae1d-13a6764e43d7
async def test_migrate_db_dry_run_touches_nothing() -> None:
    """migrate_db(write=False) must neither create the ledger nor apply anything."""
    with (
        patch(f"{_SVC}.ensure_ledger", new=AsyncMock()) as mock_ensure,
        patch(f"{_SVC}.get_applied", new=AsyncMock(return_value=set())),
        patch(f"{_SVC}.apply_migration", new=AsyncMock()) as mock_apply,
    ):
        report = await migrate_db(write=False)

    mock_ensure.assert_not_called()
    mock_apply.assert_not_called()
    assert report.write is False
    assert report.pending_before == load_policy()["migrations"]["order"]
    assert report.results == []


# ID: bb6f3087-b9ee-4569-8ca3-8439e4afdee9
async def test_migrate_db_write_applies_pending_in_manifest_order() -> None:
    order = load_policy()["migrations"]["order"]
    already = set(order[:-2])  # everything but the last two
    seen: list[str] = []

    async def fake_apply(entry, sql_path, *, session_factory):  # type: ignore[no-untyped-def]
        seen.append(entry.id)
        assert sql_path.name == entry.id
        return MigrationResult(entry.id, MigrationOutcome.APPLIED, 1)

    with (
        patch(f"{_SVC}.ensure_ledger", new=AsyncMock()) as mock_ensure,
        patch(f"{_SVC}.get_applied", new=AsyncMock(return_value=already)),
        patch(f"{_SVC}.apply_migration", new=fake_apply),
    ):
        report = await migrate_db(write=True)

    mock_ensure.assert_awaited_once()
    assert seen == order[-2:]
    assert report.applied == order[-2:]
    assert report.reconciled == [] and report.skipped == []


# ID: 8d4efa43-7d19-4858-8257-5e54e9f7399f
async def test_migrate_db_write_stops_at_first_failure() -> None:
    order = load_policy()["migrations"]["order"]
    seen: list[str] = []

    async def fake_apply(entry, sql_path, *, session_factory):  # type: ignore[no-untyped-def]
        seen.append(entry.id)
        if len(seen) == 2:
            raise RuntimeError("boom")
        return MigrationResult(entry.id, MigrationOutcome.APPLIED, 1)

    with (
        patch(f"{_SVC}.ensure_ledger", new=AsyncMock()),
        patch(f"{_SVC}.get_applied", new=AsyncMock(return_value=set())),
        patch(f"{_SVC}.apply_migration", new=fake_apply),
        pytest.raises(
            MigrationServiceError, match=f"{order[1]}.*rolled back; not recorded"
        ),
    ):
        await migrate_db(write=True)

    assert seen == order[:2], "nothing after the failing migration may be attempted"


# ID: 48c1068d-e3c8-4a07-a23d-a551000f8283
async def test_migrate_db_reports_manifest_errors_as_service_errors() -> None:
    with (
        patch(f"{_SVC}.load_manifest", side_effect=ValueError("bad manifest")),
        pytest.raises(MigrationServiceError, match="bad manifest"),
    ):
        await migrate_db(write=False)


# ---------------------------------------------------------------------------
# bootstrap_migrations() — orchestration only (retired by U4 per ADR-162 D3)
# ---------------------------------------------------------------------------


# ID: 35aadbd2-e550-48de-8dfd-27f1668b0fdd
async def test_bootstrap_seeds_pending_entries() -> None:
    """bootstrap_migrations() records every un-applied manifest entry."""
    recorded: list[str] = []

    async def fake_record(mig_id: str, *, reconciled: bool, session_factory) -> bool:  # type: ignore[no-untyped-def]
        assert reconciled is False
        recorded.append(mig_id)
        return True

    with (
        patch(f"{_SVC}.ensure_ledger", new=AsyncMock()),
        patch(f"{_SVC}.get_applied", new=AsyncMock(return_value=set())),
        patch(f"{_SVC}.record_ledger_row", new=fake_record),
    ):
        result = await bootstrap_migrations()

    expected = load_policy()["migrations"]["order"]
    assert recorded == expected
    assert result == expected


# ID: 2266358d-8e7f-4f11-82d0-04c5c7c37c7d
async def test_bootstrap_skips_already_applied() -> None:
    """bootstrap_migrations() must not re-record already-applied migrations."""
    all_migs = set(load_policy()["migrations"]["order"])

    with (
        patch(f"{_SVC}.ensure_ledger", new=AsyncMock()),
        patch(f"{_SVC}.get_applied", new=AsyncMock(return_value=all_migs)),
        patch(f"{_SVC}.record_ledger_row", new=AsyncMock()) as mock_record,
    ):
        result = await bootstrap_migrations()

    mock_record.assert_not_called()
    assert result == []
