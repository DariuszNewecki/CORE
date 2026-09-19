# tests/shared/infrastructure/migrations/test_hop_equivalence_postgres.py
"""ADR-162 D5 (R5-A) — hop equivalence: ``schema.sql`` at the previous release
plus the manifest entries added since must produce the current ``schema.sql``.

For every declared baseline that has a committed schema fixture
(``tests/fixtures/schema/schema-<tag>.sql``), two databases are built on the
disposable Postgres:

* **hop** — the baseline's released ``schema.sql``, then
  ``migrate --adopt-baseline <tag> --write`` and ``migrate --write`` with the
  real manifest and files (the operator's upgrade);
* **current** — the repository's ``schema.sql`` (a fresh install).

Both are dumped with the server's own ``pg_dump --schema-only --no-owner
--no-acl`` and compared after normalisation (comments, session settings and
the fresh-install ledger seed removed). Any difference is printed as a
unified diff.

The immediately previous release is the hop D5 makes a release obligation
("each hop is tested when it is current", D4); it must pass. Older
baselines are chained hops: a failure there is real drift that was never
tested when it was current. v2.9.1 is such a case (see the marker below) —
recorded as a strict expected failure so the drift stays visible in CI and
the marker must be removed the moment it is repaired.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from shared.infrastructure.repositories.db.common import REPO_ROOT
from shared.infrastructure.repositories.db.manifest import load_manifest
from shared.infrastructure.repositories.db.migration_service import (
    adopt_baseline,
    migrate_db,
)
from shared.infrastructure.repositories.db.schema_dump import (
    diff_schema_dumps,
    normalise_schema_dump,
)


if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from .conftest import FreshDatabase


pytestmark = [pytest.mark.integration]

assert REPO_ROOT is not None
SCHEMA_SQL = REPO_ROOT / "schema.sql"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "schema"

# Known chained-hop drift: the v2.9.1..v2.10.1 span changed the live schema
# without migration files for `core_archive` (schema), `audit_findings.run_id`
# (+ its indexes and FK), `users.display_name` and the `runtime_settings`
# drop. Discovered by this test on 2026-09-19 (ADR-162 U5); the repair is a
# Governor decision (backfill migrations), not a test adjustment. Strict: the
# xfail fails the suite once the hop becomes equivalent, forcing its removal.
KNOWN_DRIFT: dict[str, str] = {
    "v2.9.1": (
        "v2.9.1 -> current drift without migration files: core_archive schema, "
        "audit_findings.run_id (+indexes, FK), users.display_name, runtime_settings "
        "drop — see ADR-162 Phase B closeout"
    ),
}


def _baseline_params() -> list:
    params = []
    for baseline in load_manifest().baselines:
        marks = []
        if baseline.tag in KNOWN_DRIFT:
            marks.append(
                pytest.mark.xfail(reason=KNOWN_DRIFT[baseline.tag], strict=True)
            )
        params.append(pytest.param(baseline.tag, marks=marks, id=baseline.tag))
    return params


@pytest.mark.parametrize("tag", _baseline_params())
# ID: 1016f13d-0d6a-4019-960f-e72e8ddc2496
async def test_hop_from_baseline_equals_current_schema(
    tag: str,
    database_factory: Callable[[], Awaitable[FreshDatabase]],
    schema_dumper: Callable[[str], str],
) -> None:
    fixture = FIXTURES / f"schema-{tag}.sql"
    if not fixture.is_file():
        pytest.skip(f"no committed schema fixture for baseline {tag}")

    hop = await database_factory()
    await hop.load_schema(fixture)
    await adopt_baseline(tag, write=True, session_factory=hop.session_factory)
    report = await migrate_db(write=True, session_factory=hop.session_factory)
    assert report.pending_before, f"nothing to replay after {tag}?"

    current = await database_factory()
    await current.load_schema(SCHEMA_SQL)

    diff = diff_schema_dumps(
        normalise_schema_dump(schema_dumper(current.name)),
        normalise_schema_dump(schema_dumper(hop.name)),
        expected_label="schema.sql (fresh install)",
        actual_label=f"schema-{tag}.sql + manifest replay",
    )
    assert not diff, "hop is not equivalent to the fresh install:\n" + "\n".join(diff)


# ID: 34409e6f-1f78-4be6-a550-4342b4955a28
def test_the_previous_release_has_a_schema_fixture_so_the_hop_is_always_tested() -> (
    None
):
    """The latest declared baseline is the previous release (D4); without its
    fixture the D5 hop would silently skip."""
    latest = load_manifest().baselines[-1]
    assert (FIXTURES / f"schema-{latest.tag}.sql").is_file(), latest.tag
    assert latest.tag not in KNOWN_DRIFT, "the previous-release hop must be equivalent"
