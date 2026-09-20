# tests/shared/infrastructure/test_schema_ledger_seed.py
"""ADR-162 D9 — ``schema.sql`` carries an exact fresh-install ledger seed.

Hermetic: the seed block's ids must equal the manifest order exactly, and the
generator (``infra/scripts/render_ledger_seed.py``, called by
``infra/scripts/reset_test_db.sh``) must reproduce the committed block
byte-for-byte — so ``schema.sql`` and the manifest cannot drift apart without
this test failing.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from shared.infrastructure.repositories.db.common import REPO_ROOT
from shared.infrastructure.repositories.db.ledger_seed import (
    SEED_BEGIN,
    SEED_END,
    parse_ledger_seed,
    render_ledger_seed,
    strip_ledger_seed,
)
from shared.infrastructure.repositories.db.manifest import load_manifest


assert REPO_ROOT is not None
SCHEMA_SQL = REPO_ROOT / "schema.sql"
RENDER_SCRIPT = REPO_ROOT / "infra" / "scripts" / "render_ledger_seed.py"


# ID: d5991161-6886-42e0-8c32-7346733358d1
def test_schema_sql_seed_ids_equal_manifest_order() -> None:
    seed = parse_ledger_seed(SCHEMA_SQL.read_text(encoding="utf-8"))
    assert seed == list(load_manifest().order)


# ID: b978dbe1-2724-47a3-bb53-734a9aa9273b
def test_schema_sql_seed_block_is_exactly_what_the_generator_renders() -> None:
    schema = SCHEMA_SQL.read_text(encoding="utf-8")
    rendered = render_ledger_seed(load_manifest().order)
    assert schema.endswith(rendered), (
        "schema.sql's seed block differs from the generator output; regenerate with "
        "`poetry run python infra/scripts/render_ledger_seed.py`"
    )
    assert schema.count(SEED_BEGIN) == 1 and schema.count(SEED_END) == 1


# ID: bdb0fb16-1606-4695-b2c9-9a35b8a19b08
def test_seed_block_follows_the_ledger_table_definition() -> None:
    schema = SCHEMA_SQL.read_text(encoding="utf-8")
    assert schema.index("CREATE TABLE core._migrations (") < schema.index(SEED_BEGIN)
    assert "reconciled boolean DEFAULT false NOT NULL" in schema


# ID: 5537e346-7741-4f58-a136-20b752ac6593
def test_generator_script_prints_the_block() -> None:
    proc = subprocess.run(
        [sys.executable, str(RENDER_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={"PYTHONPATH": str(REPO_ROOT / "src"), "PATH": ""},
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-500:]
    assert parse_ledger_seed(proc.stdout) == list(load_manifest().order)


# ID: 24dec3d3-bb7c-451e-8612-1872efa9ff38
def test_render_parse_round_trip_and_quoting() -> None:
    order = ["001_a.sql", "002_it's.sql"]
    block = render_ledger_seed(order)
    assert parse_ledger_seed(block) == order
    assert "'002_it''s.sql'" in block


# ID: 61016a6f-3d95-4666-b629-d169d20dcdb8
def test_strip_removes_the_block_and_is_idempotent() -> None:
    body = "CREATE TABLE core._migrations (id text);\n"
    with_seed = body + "\n" + render_ledger_seed(["001_a.sql"])
    stripped = strip_ledger_seed(with_seed)
    assert SEED_BEGIN not in stripped and "001_a.sql" not in stripped
    assert stripped.strip() == body.strip()
    assert strip_ledger_seed(stripped) == stripped


@pytest.mark.parametrize(
    "text",
    [
        "no block here",
        f"{SEED_BEGIN}\nINSERT INTO core._migrations (id, reconciled) VALUES ('a', false);",
        f"{SEED_BEGIN}\nDELETE FROM core._migrations;\n{SEED_END}",
    ],
)
# ID: 6eb8e4bd-325e-4271-8ead-5d6374d91694
def test_malformed_blocks_are_refused(text: str) -> None:
    with pytest.raises(ValueError):
        parse_ledger_seed(text)
