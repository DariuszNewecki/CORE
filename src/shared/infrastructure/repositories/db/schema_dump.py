# src/shared/infrastructure/repositories/db/schema_dump.py
"""
Normalised ``pg_dump --schema-only`` comparison (ADR-162 D5, U5).

CONSTITUTIONAL AUTHORITY: Infrastructure (coordination) — pure text
processing; no I/O, no database access.

``schema.sql`` is authoritative for a fresh install and the manifest for an
upgrade (D5). CI proves the two roads meet: ``schema.sql`` at the previous
release plus the manifest entries added since must produce the current
``schema.sql``. The proof compares two ``pg_dump --schema-only --no-owner
--no-acl`` outputs after dropping everything that is not schema: comments,
session ``SET`` lines, ``\\restrict`` markers, blank lines and the fresh-install
ledger seed (data, not structure).
"""

from __future__ import annotations

import difflib
from collections.abc import Iterable

from .ledger_seed import SEED_BEGIN, SEED_END


_DROP_PREFIXES = (
    "--",
    "SET ",
    "SELECT pg_catalog.set_config",
    "\\restrict",
    "\\unrestrict",
)


# ID: 036c5d56-c261-48f6-b645-c44469cb2f8e
def normalise_schema_dump(dump: str) -> list[str]:
    """The structural lines of a schema dump, in dump order."""
    lines: list[str] = []
    in_seed = False
    for raw in dump.splitlines():
        stripped = raw.strip()
        if stripped == SEED_BEGIN:
            in_seed = True
            continue
        if stripped == SEED_END:
            in_seed = False
            continue
        if in_seed or not stripped or stripped.startswith(_DROP_PREFIXES):
            continue
        lines.append(raw.rstrip())
    return lines


# ID: b403a255-e490-4997-981d-ad65062b0608
def diff_schema_dumps(
    expected: Iterable[str],
    actual: Iterable[str],
    *,
    expected_label: str,
    actual_label: str,
) -> list[str]:
    """Unified diff between two normalised dumps; empty when equivalent."""
    return list(
        difflib.unified_diff(
            list(expected),
            list(actual),
            fromfile=expected_label,
            tofile=actual_label,
            lineterm="",
            n=2,
        )
    )
