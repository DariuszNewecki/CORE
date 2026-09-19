# tests/shared/infrastructure/test_migration_sql.py
"""ADR-162 D7 — migration SQL preparation and the transaction-control lint.

Hermetic: pure text processing plus a read of every file in the migrations
directory. The lint half is the CI guard the ruling asks for: a migration
file MAY carry a leading ``BEGIN;`` and a trailing ``COMMIT;`` and MUST NOT
carry any other transaction control or a non-transactional statement.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.infrastructure.repositories.db.common import REPO_ROOT
from shared.infrastructure.repositories.db.manifest import load_manifest
from shared.infrastructure.repositories.db.migration_sql import (
    MigrationSqlError,
    NonTransactionalStatementError,
    TransactionControlError,
    lint_migration_file,
    prepare_migration_sql,
)


assert REPO_ROOT is not None
MIGRATIONS_DIR = REPO_ROOT / "infra" / "scripts" / "migrations"


# ── every migration on disk is atomically executable ─────────────────────────


@pytest.mark.parametrize(
    "sql_file",
    sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql")),
)
# ID: ef92d16f-f5aa-41f7-b408-ab913d006a79
def test_every_migration_file_passes_the_transaction_lint(sql_file: str) -> None:
    prepared = lint_migration_file(MIGRATIONS_DIR / sql_file)
    assert prepared.statements, f"{sql_file} prepared to zero statements"
    for stmt in prepared.statements:
        # Nothing that survives preparation may be transaction control.
        head = stmt.lstrip().split(None, 1)[0].upper().rstrip(";")
        assert head not in {"BEGIN", "COMMIT", "END", "ROLLBACK", "SAVEPOINT"}, (
            f"{sql_file}: transaction control survived preparation: {head}"
        )


# ID: 5a01aa3b-8389-4bd7-a67d-708dceeca457
def test_every_manifest_entry_is_lintable() -> None:
    manifest = load_manifest()
    for entry in manifest.entries:
        lint_migration_file(manifest.sql_path(entry.id, REPO_ROOT))


# ── stripping rules ──────────────────────────────────────────────────────────


# ID: 1d0c1a88-b2c4-4032-a966-64004ed64257
def test_leading_begin_and_trailing_commit_are_stripped() -> None:
    prepared = prepare_migration_sql(
        "BEGIN;\n-- note\nCREATE TABLE t (x int);\nINSERT INTO t VALUES (1);\nCOMMIT;\n"
        "-- trailing commentary after COMMIT is fine\n"
    )
    assert prepared.stripped_leading_begin is True
    assert prepared.stripped_trailing_commit is True
    assert [s.split("\n")[-1] for s in prepared.statements] == [
        "CREATE TABLE t (x int);",
        "INSERT INTO t VALUES (1);",
    ]


@pytest.mark.parametrize(
    "sql",
    [
        "start transaction; select 1; end;",
        "Begin;\nselect 1;\nCommit;",
    ],
)
# ID: 70c91d31-d67f-4325-a385-4a1f7f6e73e2
def test_control_keyword_variants_are_recognised(sql: str) -> None:
    prepared = prepare_migration_sql(sql)
    assert prepared.stripped_leading_begin and prepared.stripped_trailing_commit
    assert len(prepared.statements) == 1


# ID: 73b4ca95-9f7c-450c-88a5-734beaef83d5
def test_files_without_transaction_control_are_unchanged() -> None:
    prepared = prepare_migration_sql(
        "CREATE TABLE t (x int);\nINSERT INTO t VALUES (1);"
    )
    assert not prepared.stripped_leading_begin
    assert not prepared.stripped_trailing_commit
    assert len(prepared.statements) == 2


# ID: f871e3f2-c175-459f-b197-870f95444123
def test_comment_only_chunks_are_dropped_but_inline_comments_kept() -> None:
    prepared = prepare_migration_sql(
        "-- header only\n\nSELECT 1; -- keep me\n-- footer"
    )
    assert len(prepared.statements) == 1
    assert "keep me" in prepared.statements[0]


# ID: 73773fcc-bf94-417c-bf4b-3aa6e8f91abb
def test_plpgsql_bodies_are_not_mistaken_for_transaction_control() -> None:
    prepared = prepare_migration_sql(
        "DO $$ BEGIN RAISE NOTICE 'x'; END $$;\n"
        "CREATE FUNCTION f() RETURNS void AS $$ BEGIN PERFORM 1; END $$ LANGUAGE plpgsql;"
    )
    assert len(prepared.statements) == 2


# ── refusals ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE t (x int);\nCOMMIT;\nCREATE TABLE u (x int);",  # mid-file COMMIT
        "BEGIN;\nCREATE TABLE t (x int);\nROLLBACK;",  # rollback
        "SAVEPOINT a;\nCREATE TABLE t (x int);",  # savepoint
        "BEGIN;\nSELECT 1;\nBEGIN;\nSELECT 2;\nCOMMIT;",  # nested begin
        "SELECT 1;\nRELEASE SAVEPOINT a;",  # release
        "BEGIN;\nSELECT 1;\nCOMMIT;\nCOMMIT;",  # double commit
    ],
)
# ID: d24ba439-59d8-40a9-ba21-8d01ce7eda4d
def test_foreign_transaction_control_is_refused(sql: str) -> None:
    with pytest.raises(TransactionControlError):
        prepare_migration_sql(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE INDEX CONCURRENTLY i ON t (x);",
        "DROP INDEX CONCURRENTLY i;",
        "VACUUM t;",
        "ALTER TYPE mood ADD VALUE 'happy';",
        "CREATE DATABASE x;",
        "ALTER SYSTEM SET work_mem = '1GB';",
    ],
)
# ID: aac2708b-7e03-4a61-8e21-b0a8d8497287
def test_non_transactional_statements_are_refused(sql: str) -> None:
    with pytest.raises(NonTransactionalStatementError):
        prepare_migration_sql(sql)


# ID: ee720074-9541-48c4-b5a3-41ea8edd4c0f
def test_errors_name_the_source_and_position() -> None:
    with pytest.raises(
        MigrationSqlError, match=r"x\.sql: statement 2 is transaction control"
    ):
        prepare_migration_sql("SELECT 1;\nCOMMIT;\nSELECT 2;", source="x.sql")


# ID: 3073360d-d275-4874-a961-ad8d26eac170
def test_lint_reads_the_file(tmp_path: Path) -> None:
    p = tmp_path / "m.sql"
    p.write_text("BEGIN;\nSELECT 1;\nCOMMIT;\n", encoding="utf-8")
    assert lint_migration_file(p).statements == ("SELECT 1;",)
