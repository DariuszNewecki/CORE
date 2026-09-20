# src/shared/infrastructure/repositories/db/ledger_seed.py
"""
The fresh-install migration ledger seed carried by ``schema.sql`` (ADR-162 D9).

CONSTITUTIONAL AUTHORITY: Infrastructure (coordination) — renders and parses a
deterministic SQL block; decides nothing.

``schema.sql`` is authoritative for a fresh install (D5): it already contains
every change the manifest records, so a fresh database must start with a
COMPLETE ledger, not an empty one — an empty ledger on a populated schema is
a refusal state (D2), never a silent one. The generator step in
``infra/scripts/reset_test_db.sh`` appends the block this module renders;
``tests/shared/infrastructure/test_schema_ledger_seed.py`` proves the block's
ids equal the manifest order exactly.

This module only renders and parses text. Printing the block for the current
manifest is a script surface, not logic-layer work
(``architecture.channels.logic_no_terminal_rendering``)::

    poetry run python infra/scripts/render_ledger_seed.py
"""

from __future__ import annotations

from collections.abc import Iterable


SEED_BEGIN = "-- CORE-LEDGER-SEED-BEGIN"
SEED_END = "-- CORE-LEDGER-SEED-END"

_HEADER = """\
--
-- CORE migration ledger seed (ADR-162 D9). Generated from
-- infra/migrations/manifest.yaml by infra/scripts/reset_test_db.sh so that a
-- fresh install starts with a complete ledger. Do not edit by hand; regenerate
-- with: poetry run python infra/scripts/render_ledger_seed.py
--
"""


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


# ID: 89c9dd0d-d475-4d6a-9ac9-ec1144226393
def render_ledger_seed(order: Iterable[str]) -> str:
    """The SQL block that records every manifest entry as applied at install time.

    ``applied_at`` is left to its ``now()`` default — the moment the schema
    was loaded is the truthful application time; ``reconciled`` is false:
    the rows describe what ``schema.sql`` itself already contains.
    """
    lines = [_HEADER, SEED_BEGIN]
    lines.extend(
        f"INSERT INTO core._migrations (id, reconciled) VALUES ({_quote(mig)}, false);"
        for mig in order
    )
    lines.append(SEED_END)
    return "\n".join(lines) + "\n"


# ID: c168ed1d-3474-448a-947a-0afdb2ba753d
def parse_ledger_seed(schema_text: str) -> list[str]:
    """The ids the seed block in ``schema_text`` records, in order.

    Raises ``ValueError`` when the block is missing, unterminated or contains
    anything other than the expected INSERT statements.
    """
    try:
        start = schema_text.index(SEED_BEGIN) + len(SEED_BEGIN)
        end = schema_text.index(SEED_END, start)
    except ValueError as exc:
        raise ValueError("schema.sql carries no complete ledger seed block") from exc
    ids: list[str] = []
    prefix = "INSERT INTO core._migrations (id, reconciled) VALUES ('"
    suffix = "', false);"
    for raw in schema_text[start:end].splitlines():
        line = raw.strip()
        if not line:
            continue
        if not (line.startswith(prefix) and line.endswith(suffix)):
            raise ValueError(f"unexpected line in ledger seed block: {line[:80]!r}")
        ids.append(line[len(prefix) : -len(suffix)].replace("''", "'"))
    return ids


# ID: 73965374-6ec6-408e-885f-1e80da49413d
def strip_ledger_seed(schema_text: str) -> str:
    """``schema_text`` without its seed block (header included), if any."""
    if _HEADER.strip() not in schema_text:
        return schema_text
    start = schema_text.index(_HEADER.strip())
    end = schema_text.index(SEED_END, start) + len(SEED_END)
    return schema_text[:start].rstrip("\n") + "\n" + schema_text[end:].lstrip("\n")
