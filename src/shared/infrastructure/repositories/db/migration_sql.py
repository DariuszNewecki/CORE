# src/shared/infrastructure/repositories/db/migration_sql.py
"""
Migration SQL preparation: statement splitting, transaction-control stripping
and the fail-closed lint that keeps every migration runnable in ONE transaction.

CONSTITUTIONAL AUTHORITY: Infrastructure (coordination) — pure text processing,
no I/O, no database access, no decisions about *which* migration to run.

ADR-162 D7 (R7-A): the ledger engine executes a migration's statements and its
ledger row in a single transaction. That is only possible if the engine owns
transaction control. Migration files may keep a leading ``BEGIN;`` and a
trailing ``COMMIT;`` (readable with ``psql -f``); the engine strips exactly
those two. Any other transaction control (a mid-file ``COMMIT``, ``ROLLBACK``,
``SAVEPOINT``, …) would silently break atomicity and is refused. Statements
that PostgreSQL cannot run inside a transaction block (``CREATE INDEX
CONCURRENTLY``, ``VACUUM``, ``ALTER TYPE … ADD VALUE``, …) are refused as well:
non-transactional migrations are unsupported until designed (D7, fail closed).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import sqlparse


# Transaction-control statements. ``END`` is PostgreSQL's alias for ``COMMIT``.
_TX_CONTROL_RE = re.compile(
    r"^(?P<kw>BEGIN|START\s+TRANSACTION|COMMIT|END|ROLLBACK|SAVEPOINT|RELEASE"
    r"(?:\s+SAVEPOINT)?|ABORT|PREPARE\s+TRANSACTION)\b",
    re.IGNORECASE,
)

# Statement shapes PostgreSQL refuses inside a transaction block. Detected on the
# comment-stripped statement text; each is a whole-statement property, so a
# match anywhere in the statement is disqualifying.
_NON_TRANSACTIONAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "CREATE/DROP/REINDEX ... CONCURRENTLY",
        re.compile(r"\bCONCURRENTLY\b", re.IGNORECASE),
    ),
    ("VACUUM", re.compile(r"^\s*VACUUM\b", re.IGNORECASE)),
    (
        "ALTER TYPE ... ADD VALUE",
        re.compile(r"^\s*ALTER\s+TYPE\b.*\bADD\s+VALUE\b", re.IGNORECASE | re.DOTALL),
    ),
    (
        "CREATE/DROP DATABASE",
        re.compile(r"^\s*(CREATE|DROP)\s+DATABASE\b", re.IGNORECASE),
    ),
    (
        "CREATE/DROP TABLESPACE",
        re.compile(r"^\s*(CREATE|DROP)\s+TABLESPACE\b", re.IGNORECASE),
    ),
    (
        "ALTER SYSTEM",
        re.compile(r"^\s*ALTER\s+SYSTEM\b", re.IGNORECASE),
    ),
    ("DISCARD ALL", re.compile(r"^\s*DISCARD\s+ALL\b", re.IGNORECASE)),
)


# ID: 958b235c-4781-475a-8a32-a7cf21f8a3ee
class MigrationSqlError(ValueError):
    """A migration file cannot be executed atomically by the ledger engine."""


# ID: 25a003f9-3789-4bae-b8b6-03b5b1a524e8
class TransactionControlError(MigrationSqlError):
    """Transaction control other than a leading BEGIN / trailing COMMIT."""


# ID: 68b12328-379b-466b-bd54-aba2f3ce79ac
class NonTransactionalStatementError(MigrationSqlError):
    """A statement PostgreSQL refuses inside a transaction block."""


@dataclass(frozen=True)
# ID: 9258ea47-303c-43e3-b4a5-fde533d0f84f
class PreparedMigration:
    """The executable form of one migration file."""

    statements: tuple[str, ...]
    stripped_leading_begin: bool
    stripped_trailing_commit: bool


def _normalise(statement: str) -> str:
    """Comment-free, whitespace-trimmed, without the trailing semicolon."""
    bare = sqlparse.format(statement, strip_comments=True).strip()
    return bare.rstrip(";").strip()


# ID: a0755d08-6b21-4af2-aa24-2be3298f2bed
def prepare_migration_sql(sql_text: str, *, source: str = "<sql>") -> PreparedMigration:
    """Split ``sql_text`` into engine-executable statements.

    Rules (ADR-162 D7):
      * a leading ``BEGIN`` and a trailing ``COMMIT``/``END`` are stripped —
        the engine supplies the transaction;
      * any other transaction control raises :class:`TransactionControlError`;
      * any statement PostgreSQL cannot run inside a transaction block raises
        :class:`NonTransactionalStatementError`;
      * comment-only chunks are dropped; the original statement text (with
        its comments) is preserved for everything that is executed.

    Pure: no I/O. ``source`` only labels error messages.
    """
    chunks = [s for s in sqlparse.split(sql_text) if s.strip()]
    # (original text, normalised text) for chunks that carry a statement.
    real: list[tuple[str, str]] = []
    for chunk in chunks:
        norm = _normalise(chunk)
        if norm:
            real.append((chunk.strip(), norm))

    stripped_begin = False
    stripped_commit = False
    if real and _is_control(real[0][1], {"BEGIN", "START TRANSACTION"}):
        real.pop(0)
        stripped_begin = True
    if real and _is_control(real[-1][1], {"COMMIT", "END"}):
        real.pop()
        stripped_commit = True

    statements: list[str] = []
    for position, (original, norm) in enumerate(real, start=1):
        control = _TX_CONTROL_RE.match(norm)
        if control:
            raise TransactionControlError(
                f"{source}: statement {position} is transaction control "
                f"({control.group('kw').upper()}); only a leading BEGIN and a "
                "trailing COMMIT are permitted in a migration file (ADR-162 D7)"
            )
        for label, pattern in _NON_TRANSACTIONAL_PATTERNS:
            if pattern.search(norm):
                raise NonTransactionalStatementError(
                    f"{source}: statement {position} ({label}) cannot run inside "
                    "a transaction block; non-transactional migrations are "
                    "unsupported until designed (ADR-162 D7)"
                )
        statements.append(original)

    return PreparedMigration(
        statements=tuple(statements),
        stripped_leading_begin=stripped_begin,
        stripped_trailing_commit=stripped_commit,
    )


def _is_control(norm: str, keywords: set[str]) -> bool:
    collapsed = re.sub(r"\s+", " ", norm).upper()
    return collapsed in keywords


# ID: 7399086c-3eef-4b8f-bd77-f2b8969ec5c5
def lint_migration_file(path: Path) -> PreparedMigration:
    """Prepare ``path`` and raise :class:`MigrationSqlError` if it is not
    atomically executable. Used by CI and by the engine before execution."""
    return prepare_migration_sql(path.read_text(encoding="utf-8"), source=path.name)
