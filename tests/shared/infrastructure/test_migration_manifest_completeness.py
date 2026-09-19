# tests/shared/infrastructure/test_migration_manifest_completeness.py
"""ADR-162 D6 / D12 §2-3 / D10 — the manifest is complete, probed and immutable.

Hermetic guards (CI):
  * bidirectional manifest <-> disk: every entry has a file, every ``.sql``
    file is an entry, each exactly once, no unmanaged list;
  * both ``20260722_active_finding_*`` files are ledgered, in date position;
  * every entry after the v2.9.1 baseline declares a ``verify`` probe;
    reconcilable entries are the explicitly ruled ones only;
  * declared baselines cover every tagged release from v2.9.1 (D4);
  * released migration bytes are unchanged (pinned sha256 at v2.10.1);
  * the committed v2.9.1 schema fixture is byte-identical to the tag (checked
    when the tag is reachable; CI's shallow checkout skips it).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from shared.infrastructure.repositories.db.common import REPO_ROOT
from shared.infrastructure.repositories.db.manifest import (
    ManifestError,
    load_manifest,
    parse_manifest,
    verify_manifest_matches_disk,
)


assert REPO_ROOT is not None
MIGRATIONS_DIR = REPO_ROOT / "infra" / "scripts" / "migrations"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "schema"
RELEASED = json.loads((FIXTURES / "released_migrations_sha256.json").read_text("utf-8"))

DEDUP = "20260722_active_finding_dedup.sql"
RECONCILE = "20260722_active_finding_reconcile.sql"
RECONCILED_COLUMN = "20260919_adr162_migrations_reconciled.sql"


# ── bidirectional completeness (D6, D12 §3) ──────────────────────────────────


# ID: 514d7280-4d41-4e60-8504-ab13e1593dbc
def test_every_sql_file_on_disk_is_ledgered_exactly_once() -> None:
    manifest = load_manifest(verify_disk=False)
    on_disk = sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql"))
    assert sorted(manifest.order) == on_disk
    assert len(set(manifest.order)) == len(manifest.order)


# ID: 29bf6fd5-8457-4912-9bb5-317730914c2f
def test_every_manifest_entry_exists_on_disk() -> None:
    manifest = load_manifest(verify_disk=False)
    missing = [m for m in manifest.order if not (MIGRATIONS_DIR / m).is_file()]
    assert missing == []


# ID: 8812925d-526b-4d0d-be47-04f0853ddfd1
def test_load_manifest_verifies_disk_by_default() -> None:
    load_manifest()  # raises ManifestError on any disagreement


# ID: 3ee98102-6163-474d-acdb-994c702c3da8
def test_disk_verification_refuses_unledgered_and_missing_files(tmp_path: Path) -> None:
    (tmp_path / "m").mkdir()
    (tmp_path / "m" / "001_a.sql").write_text("select 1;", encoding="utf-8")
    (tmp_path / "m" / "002_stray.sql").write_text("select 1;", encoding="utf-8")
    manifest = parse_manifest(
        {"migrations": {"directory": "m", "order": ["001_a.sql", "003_gone.sql"]}}
    )
    with pytest.raises(ManifestError) as excinfo:
        verify_manifest_matches_disk(manifest, tmp_path)
    assert "003_gone.sql" in str(excinfo.value)
    assert "002_stray.sql" in str(excinfo.value)


# ID: 6786e386-b414-4289-b23e-dd69b44a13ad
def test_no_unmanaged_escape_hatch_key() -> None:
    """D12 §3: an ``unmanaged:`` list is not a recognised manifest key."""
    with pytest.raises(ManifestError, match="unknown keys"):
        parse_manifest(
            {
                "migrations": {
                    "directory": "x",
                    "order": ["001_a.sql"],
                    "unmanaged": ["002_b.sql"],
                }
            }
        )


# ── the two hand-applied files are ledgered in date position (D6) ───────────


# ID: 4ebef44a-a0d4-4416-bbe6-fbd1045fa611
def test_20260722_entries_are_ledgered_between_their_date_neighbours() -> None:
    order = load_manifest().order
    i_dedup, i_rec = order.index(DEDUP), order.index(RECONCILE)
    assert i_rec == i_dedup + 1, "dedup (columns) must precede reconcile (index)"
    assert order[i_dedup - 1].startswith("20260717_")
    assert order[i_rec + 1].startswith("20260727_")
    assert list(order) == sorted(order)


# ── probe policy (D3, D12 §2) ────────────────────────────────────────────────


# ID: 7a28fcaa-c339-41e1-858f-c640346a0d27
def test_every_entry_after_the_v2_9_1_baseline_declares_a_verify_probe() -> None:
    manifest = load_manifest()
    through = manifest.baseline("v2.9.1").through
    after = manifest.entries[manifest.order.index(through) + 1 :]
    assert after, "the span after v2.9.1 must not be empty"
    missing = [e.id for e in after if not e.verify]
    assert missing == [], f"entries without a verify probe: {missing}"


# ID: c0b0ad58-f5e9-4d2c-8d9e-a2493f3c5b64
def test_reconcilable_entries_are_exactly_the_ruled_ones() -> None:
    """Reconciliation is exceptional (D12 §2): only the two files applied by
    hand before they were ledgered, plus the ledger's own column (which the
    engine creates before it can record anything)."""
    manifest = load_manifest()
    assert sorted(e.id for e in manifest.entries if e.reconcilable) == sorted(
        [DEDUP, RECONCILE, RECONCILED_COLUMN]
    )
    for e in manifest.entries:
        if e.reconcilable:
            assert e.verify, f"{e.id}: reconcilable without a probe"


# ID: 0c34efee-48f1-4b22-a36c-34eaa6581731
def test_no_entry_is_declared_non_transactional() -> None:
    assert [e.id for e in load_manifest().entries if not e.transactional] == []


# ID: f6df8df6-a309-49bd-82cc-f2b51051d057
def test_probes_are_single_select_statements() -> None:
    """Probes are read-only by construction: one SELECT, no semicolons, no DML."""
    manifest = load_manifest()
    queries = [e.verify for e in manifest.entries if e.verify]
    for b in manifest.baselines:
        queries.extend(b.probes)
    for q in queries:
        lowered = q.strip().lower()
        assert lowered.startswith("select "), q[:80]
        assert ";" not in lowered, q[:80]
        for verb in ("insert ", "update ", "delete ", "alter ", "create ", "drop "):
            assert verb not in lowered, f"{verb!r} in probe: {q[:80]}"


# ── baselines (D3, D4) ───────────────────────────────────────────────────────


# ID: d50a07d8-99f0-4280-9a17-b7794badef1b
def test_baselines_cover_every_tagged_release_from_v2_9_1() -> None:
    manifest = load_manifest()
    tags = [b.tag for b in manifest.baselines]
    assert tags[:2] == ["v2.9.1", "v2.10.1"]
    assert manifest.baseline("v2.9.1").through.startswith("20260628_")
    assert manifest.baseline("v2.10.1").through.startswith("20260914_885_")
    # v2.10.1 shipped every entry before the 20260919 ledger column — including
    # the two 20260722 files, which its schema.sql already carried.
    v2_10_1 = [
        e.id for e in manifest.entries_through(manifest.baseline("v2.10.1").through)
    ]
    assert DEDUP in v2_10_1 and RECONCILE in v2_10_1
    assert RECONCILED_COLUMN not in v2_10_1


# ID: 8a380250-2caa-4bdb-a08f-c4730a3fbf35
def test_each_baseline_has_at_least_one_absence_probe_except_the_latest() -> None:
    """A baseline other than the latest must be distinguishable from the next
    one: at least one probe asserts that a later object is absent."""
    manifest = load_manifest()
    for b in manifest.baselines[:-1]:
        assert any(" is null" in p or "not exists" in p for p in b.probes), (
            f"{b.tag} has no discriminating absence probe"
        )


# ── immutability (D10) ───────────────────────────────────────────────────────


@pytest.mark.parametrize("sql_file", sorted(RELEASED["sha256"]))
# ID: b0e2a314-60ee-4e29-aa10-43e9c5a8f1a8
def test_released_migration_bytes_are_unchanged(sql_file: str) -> None:
    digest = hashlib.sha256((MIGRATIONS_DIR / sql_file).read_bytes()).hexdigest()
    assert digest == RELEASED["sha256"][sql_file], (
        f"{sql_file} differs from its released ({RELEASED['released_at']}) bytes"
    )


# ID: 1ac40a9d-94d0-4a65-a3bb-de5190d65c26
def test_v2_9_1_schema_fixture_matches_the_tag_when_reachable() -> None:
    fixture = FIXTURES / "schema-v2.9.1.sql"
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", "v2.9.1:schema.sql"],
        capture_output=True,
    )
    if proc.returncode != 0:
        pytest.skip("tag v2.9.1 not reachable in this checkout (shallow clone)")
    assert fixture.read_bytes() == proc.stdout
