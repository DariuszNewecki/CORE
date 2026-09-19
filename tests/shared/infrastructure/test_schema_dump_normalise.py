# tests/shared/infrastructure/test_schema_dump_normalise.py
"""ADR-162 D5 — the hop-equivalence comparator detects deliberate drift.

Hermetic counterpart of ``migrations/test_hop_equivalence_postgres.py``: the
normaliser must drop everything that is not schema (comments, session SET
lines, restrict markers, the ledger seed) and the differ must surface any
structural difference — a comparator that ignored a missing column would
make the CI hop test a rubber stamp.
"""

from __future__ import annotations

from shared.infrastructure.repositories.db.ledger_seed import render_ledger_seed
from shared.infrastructure.repositories.db.schema_dump import (
    diff_schema_dumps,
    normalise_schema_dump,
)


_DUMP = """\
--
-- PostgreSQL database dump
--

SET statement_timeout = 0;
SELECT pg_catalog.set_config('search_path', '', false);
\\restrict abc

CREATE SCHEMA core;


--
-- Name: t; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.t (
    id integer NOT NULL,
    name text
);
\\unrestrict abc
"""


# ID: 9a0ea5cf-4595-4c8e-888f-b300266b34c1
def test_normaliser_keeps_only_structure() -> None:
    assert normalise_schema_dump(_DUMP) == [
        "CREATE SCHEMA core;",
        "CREATE TABLE core.t (",
        "    id integer NOT NULL,",
        "    name text",
        ");",
    ]


# ID: aee0e819-8c55-4b8e-86de-24b8199ec8cc
def test_normaliser_drops_the_ledger_seed_block() -> None:
    with_seed = _DUMP + "\n" + render_ledger_seed(["001_a.sql", "002_b.sql"])
    assert normalise_schema_dump(with_seed) == normalise_schema_dump(_DUMP)


# ID: c3fa9cd2-ff62-4d14-9c07-ec7c32d2da0a
def test_equivalent_dumps_produce_no_diff() -> None:
    a = normalise_schema_dump(_DUMP)
    b = normalise_schema_dump(
        _DUMP.replace("-- Name: t;", "-- Name: t (renamed comment);")
    )
    assert diff_schema_dumps(a, b, expected_label="a", actual_label="b") == []


# ID: 2c62f72d-6bb9-4cb8-b6a3-c739a2be1eb8
def test_deliberate_drift_is_detected_and_named() -> None:
    drifted = _DUMP.replace("    name text\n", "    name text,\n    extra boolean\n")
    diff = diff_schema_dumps(
        normalise_schema_dump(_DUMP),
        normalise_schema_dump(drifted),
        expected_label="fresh",
        actual_label="hop",
    )
    assert diff, "an added column must be reported"
    assert any(line.startswith("+    extra boolean") for line in diff)
    assert diff[0].startswith("--- fresh") and diff[1].startswith("+++ hop")
