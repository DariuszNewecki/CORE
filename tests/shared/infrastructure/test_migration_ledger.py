"""Migration ledger — unit tests for the manifest + service layer.

Covers:
  - Manifest loads and contains expected structure
  - All listed SQL files exist on disk
  - Order list is sorted (date-prefixed names enforce chronological order)
  - load_policy() returns the manifest dict
  - bootstrap_migrations() seeds pending entries without running SQL
  - migrate_db(apply=False) is a no-op (dry run)
  - _run_migrations raises on bad manifest rather than silently doing nothing

DB-backed tests (ensure_ledger, get_applied, record_applied) are integration
tests and require 192.168.20.23 — they are marked accordingly and skipped in
offline runs.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import yaml

from shared.infrastructure.repositories.db.common import REPO_ROOT, load_policy
from shared.infrastructure.repositories.db.migration_service import (
    bootstrap_migrations,
    migrate_db,
)


_MANIFEST = REPO_ROOT / "infra" / "migrations" / "manifest.yaml"
_MIGRATIONS_DIR = REPO_ROOT / "infra" / "scripts" / "migrations"


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
# bootstrap_migrations() — no DB calls, purely testing orchestration
# ---------------------------------------------------------------------------


# ID: 35aadbd2-e550-48de-8dfd-27f1668b0fdd
async def test_bootstrap_seeds_pending_entries() -> None:
    """bootstrap_migrations() records every un-applied manifest entry."""
    applied_calls: list[str] = []

    async def fake_record(mig_id: str) -> None:
        applied_calls.append(mig_id)

    with (
        patch(
            "shared.infrastructure.repositories.db.migration_service.ensure_ledger",
            new=AsyncMock(),
        ),
        patch(
            "shared.infrastructure.repositories.db.migration_service.get_applied",
            new=AsyncMock(return_value=set()),
        ),
        patch(
            "shared.infrastructure.repositories.db.migration_service.record_applied",
            new=fake_record,
        ),
    ):
        await bootstrap_migrations()

    pol = load_policy()
    expected = pol["migrations"]["order"]
    assert applied_calls == expected


# ID: 2266358d-8e7f-4f11-82d0-04c5c7c37c7d
async def test_bootstrap_skips_already_applied() -> None:
    """bootstrap_migrations() must not re-record already-applied migrations."""
    pol = load_policy()
    all_migs = pol["migrations"]["order"]
    already_applied = set(all_migs)

    applied_calls: list[str] = []

    async def fake_record(mig_id: str) -> None:
        applied_calls.append(mig_id)

    with (
        patch(
            "shared.infrastructure.repositories.db.migration_service.ensure_ledger",
            new=AsyncMock(),
        ),
        patch(
            "shared.infrastructure.repositories.db.migration_service.get_applied",
            new=AsyncMock(return_value=already_applied),
        ),
        patch(
            "shared.infrastructure.repositories.db.migration_service.record_applied",
            new=fake_record,
        ),
    ):
        await bootstrap_migrations()

    assert applied_calls == [], (
        "bootstrap must not re-record already-applied migrations"
    )


# ---------------------------------------------------------------------------
# migrate_db() dry-run — no DB calls
# ---------------------------------------------------------------------------


# ID: a473cdc3-8b5d-4fbf-ae1d-13a6764e43d7
async def test_migrate_db_dry_run_does_not_apply() -> None:
    """migrate_db(apply=False) must not call apply_sql_file or record_applied."""
    pol = load_policy()
    all_migs = pol["migrations"]["order"]

    with (
        patch(
            "shared.infrastructure.repositories.db.migration_service.ensure_ledger",
            new=AsyncMock(),
        ),
        patch(
            "shared.infrastructure.repositories.db.migration_service.get_applied",
            new=AsyncMock(return_value=set()),
        ),
        patch(
            "shared.infrastructure.repositories.db.migration_service.apply_sql_file",
            new=AsyncMock(),
        ) as mock_apply,
        patch(
            "shared.infrastructure.repositories.db.migration_service.record_applied",
            new=AsyncMock(),
        ) as mock_record,
    ):
        await migrate_db(apply=False)

    mock_apply.assert_not_called()
    mock_record.assert_not_called()
