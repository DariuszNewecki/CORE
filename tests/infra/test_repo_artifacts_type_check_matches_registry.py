"""Guard against artifact_type vocabulary drift (#646 / #647).

ADR-090 D7 expanded `.intent/artifact_types/*.yaml` to 11 types, but the
`repo_artifacts_type_check` CHECK in `infra/sql/db_schema_live.sql` kept the
old set — so the crawler's inserts for adr/paper/spec_markdown/intent_json/
intent_yaml were silently rejected for ~10 days and `.specs/` never indexed.

The root cause is two sources of truth for one vocabulary: the registry (what
the crawler produces) and the DB CHECK (what the table accepts), with nothing
asserting they agree. This test is that assertion — if either side changes
without the other, it fails at CI time instead of in production.

Scope note: this guards the schema-as-truth file (`db_schema_live.sql`), which
is hand-maintained and the realistic drift vector. Keeping the live DB in sync
with that file is a separate apply-discipline concern.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA = _REPO_ROOT / "infra" / "sql" / "db_schema_live.sql"
_REGISTRY_DIR = _REPO_ROOT / ".intent" / "artifact_types"


def _check_constraint_artifact_types() -> set[str]:
    """Extract the allowed artifact_type set from repo_artifacts_type_check."""
    text = _SCHEMA.read_text(encoding="utf-8")
    m = re.search(
        r"repo_artifacts_type_check CHECK \(\(artifact_type = ANY \(ARRAY\[(.*?)\]\)\)\)",
        text,
    )
    assert m, "repo_artifacts_type_check not found in db_schema_live.sql"
    return set(re.findall(r"'([a-z_]+)'", m.group(1)))


def _registry_artifact_type_ids() -> set[str]:
    """The authoritative artifact_type ids from the .intent/ registry."""
    ids: set[str] = set()
    for f in sorted(_REGISTRY_DIR.glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        if "id" in data:
            ids.add(data["id"])
    return ids


def test_repo_artifacts_check_equals_artifact_type_registry() -> None:
    """The DB CHECK vocabulary must equal the artifact_type registry ids.

    Exact equality catches drift in both directions: a registry type the CHECK
    would reject (the #646 outage), and a stale CHECK value with no registry
    backing (e.g. the legacy 'intent' retired in #647).
    """
    check = _check_constraint_artifact_types()
    registry = _registry_artifact_type_ids()

    assert check == registry, (
        "artifact_type vocabulary drift (#646/#647) — db_schema_live.sql "
        "repo_artifacts_type_check is out of sync with .intent/artifact_types/:\n"
        f"  allowed by CHECK but not in registry: {sorted(check - registry)}\n"
        f"  in registry but rejected by CHECK:    {sorted(registry - check)}\n"
        "Update the CHECK (and the live DB constraint) to match the registry."
    )
