# tests/shared/infrastructure/test_migration_manifest.py
"""ADR-162 — typed manifest parsing and structural validation (hermetic).

``parse_manifest`` is the single gate between the YAML on disk and the ledger
engine: every shape the engine relies on (probes keyed by real entries,
reconcilable ⇒ verify, baselines chained chronologically) is refused here
rather than discovered mid-migration.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from shared.infrastructure.repositories.db.manifest import (
    ManifestError,
    load_manifest,
    parse_manifest,
)


def _policy(**overrides: Any) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "directory": "infra/scripts/migrations",
        "order": ["001_a.sql", "002_b.sql", "003_c.sql"],
    }
    cfg.update(overrides)
    return {"migrations": cfg}


# ID: dbac038e-5a69-48be-bfb9-e83322051340
def test_repository_manifest_parses() -> None:
    manifest = load_manifest()
    assert manifest.directory == Path("infra/scripts/migrations")
    assert manifest.order == tuple(e.id for e in manifest.entries)
    assert manifest.entry(manifest.order[-1]).id == manifest.order[-1]


# ID: 0fd7b9e2-fb2e-4421-ac4c-a14a2eb95215
def test_plain_entries_default_to_no_probe_non_reconcilable_transactional() -> None:
    m = parse_manifest(_policy())
    e = m.entry("002_b.sql")
    assert e.verify is None and e.reconcilable is False and e.transactional is True
    assert m.baselines == ()
    assert [e.id for e in m.entries_through("002_b.sql")] == ["001_a.sql", "002_b.sql"]
    assert m.sql_path("002_b.sql", Path("/repo")) == Path(
        "/repo/infra/scripts/migrations/002_b.sql"
    )


# ID: 109191bb-686f-4bcf-b2c3-81dff89621de
def test_probe_entries_are_typed() -> None:
    m = parse_manifest(
        _policy(
            probes={
                "002_b.sql": {"verify": " select true ", "reconcilable": True},
                "003_c.sql": {"verify": "select true", "transactional": False},
            }
        )
    )
    assert m.entry("002_b.sql").verify == "select true"
    assert m.entry("002_b.sql").reconcilable is True
    assert m.entry("003_c.sql").transactional is False


# ID: 9c4f41e8-cb89-49ee-b64a-386763ec7b22
def test_baselines_are_typed_and_ordered() -> None:
    m = parse_manifest(
        _policy(
            baselines={
                "v1": {"through": "001_a.sql", "probes": ["select true"]},
                "v2": {
                    "through": "003_c.sql",
                    "probes": ["select true", "select false"],
                },
            }
        )
    )
    assert [b.tag for b in m.baselines] == ["v1", "v2"]
    assert m.baseline("v2").through == "003_c.sql"
    assert m.baseline("v2").probes == ("select true", "select false")


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"order": []}, "non-empty list"),
        ({"order": ["001_a.sql", "001_a.sql"]}, "more than once"),
        ({"order": ["001_a.txt"]}, r"\.sql filename"),
        ({"directory": ""}, "directory"),
        ({"bogus": 1}, "unknown keys"),
        ({"probes": {"999_zz.sql": {"verify": "select true"}}}, "not in order"),
        (
            {"probes": {"001_a.sql": {"reconcilable": True}}},
            "reconcilable but declares no verify",
        ),
        ({"probes": {"001_a.sql": {"verify": ""}}}, "non-empty SQL"),
        (
            {"probes": {"001_a.sql": {"verify": "select true", "extra": 1}}},
            "unknown keys",
        ),
        (
            {"probes": {"001_a.sql": {"verify": "select true", "reconcilable": "yes"}}},
            "boolean",
        ),
        (
            {"baselines": {"v1": {"through": "nope.sql", "probes": ["select true"]}}},
            "through",
        ),
        (
            {"baselines": {"v1": {"through": "001_a.sql", "probes": []}}},
            "non-empty list",
        ),
        ({"baselines": {"v1": {"through": "001_a.sql"}}}, "probes"),
        (
            {
                "baselines": {
                    "v2": {"through": "003_c.sql", "probes": ["select true"]},
                    "v1": {"through": "001_a.sql", "probes": ["select true"]},
                }
            },
            "chronological order",
        ),
    ],
)
# ID: b7ed02cd-de77-4201-8ab0-46b65c7cf4ee
def test_structural_violations_are_refused(
    overrides: dict[str, Any], match: str
) -> None:
    with pytest.raises(ManifestError, match=match):
        parse_manifest(_policy(**overrides))


# ID: 9aa0da4f-4f89-4e17-ba29-7bb43f6ef178
def test_missing_migrations_mapping_is_refused() -> None:
    with pytest.raises(ManifestError):
        parse_manifest({"nope": {}})
