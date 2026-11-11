# src/body/services/grc/record_catalog.py

"""Load a record catalog: a catalog whose rules judge records (ADR-173 D9).

Same file format and the same ADR-174 checks as any catalog (``check_catalog``:
format schemas, provenance beside it, known engine ids), read from a path
rather than resolved under ``grc-catalogs/``: a record catalog lives with the
engine module that runs it (D15) and has no inventory entry. Warn mode as in
ADR-174: warnings are logged and the catalog still loads.

Each requirement becomes a ``RecordRule``. ``enforcement: reporting`` makes a
rule non-blocking; anything else, or nothing, keeps it blocking (D13).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from body.services.grc.catalog_contract import (
    CatalogContractWarning,
    check_catalog,
    log_warnings,
)
from mind.logic.record_contract import RecordRule


# ID: 6a1d4c2e-8b3f-4e7a-9c5d-2f0b8e1a7d34
def record_catalog_warnings(path: Path) -> list[CatalogContractWarning]:
    """The ADR-174 contract warnings for the record catalog at ``path``."""
    return check_catalog(path)


# ID: 3e9b7f1a-5c2d-4a8e-b6f0-9d1c4e7a2b58
def load_record_catalog(path: Path) -> list[RecordRule]:
    """The catalog's requirements as record rules, in catalog order."""
    log_warnings(record_catalog_warnings(path))
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [_rule(entry) for entry in data.get("requirements") or []]


def _rule(entry: dict[str, Any]) -> RecordRule:
    return RecordRule(
        rule_id=str(entry["id"]),
        engine=str(entry["engine"]),
        params=dict(entry.get("params") or {}),
        blocking=entry.get("enforcement") != "reporting",
    )
