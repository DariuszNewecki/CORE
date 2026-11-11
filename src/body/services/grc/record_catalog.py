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

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from body.services.grc.catalog_contract import (
    CatalogContractWarning,
    check_catalog,
    log_warnings,
)
from mind.logic.record_contract import (
    RecordRule,
    RecordVerdict,
    evaluate,
    record_catalogs,
)


RECORD_FORMAT = "library-snapshot/1"


# ID: 4a54db74-c609-492c-af22-f9d15f72dc7e
class RecordInputError(ValueError):
    """The record file or the catalog id cannot be used; nothing was judged."""


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


# ID: 7c7e52e3-53a5-4bb6-ac72-87296eb55f12
def resolve_record_catalog(catalog_id: str) -> Path:
    """The path of a record catalog by its id, as the engines that ship
    one declare it (ADR-173 D15)."""
    catalogs = record_catalogs()
    path = catalogs.get(catalog_id)
    if path is None:
        known = ", ".join(sorted(catalogs)) or "none"
        raise RecordInputError(
            f"unknown record catalog {catalog_id!r} (known: {known})"
        )
    if not Path(path).is_file():
        raise RecordInputError(f"record catalog {catalog_id!r} has no file at {path}")
    return Path(path)


# ID: 4ca7e7e1-703c-46bb-9265-ac170a829f97
def read_record(path: Path) -> dict[str, Any]:
    """A record file: a JSON object in format ``library-snapshot/1`` with an
    ``items`` object. Anything else raises ``RecordInputError``."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecordInputError(f"cannot read record {path}: {exc}") from exc
    if not isinstance(data, Mapping):
        raise RecordInputError(f"record {path} is not a JSON object")
    if data.get("format") != RECORD_FORMAT:
        raise RecordInputError(
            f"record {path} has format {data.get('format')!r}, expected {RECORD_FORMAT!r}"
        )
    if not isinstance(data.get("items"), Mapping):
        raise RecordInputError(f"record {path} has no items object")
    return dict(data)


# ID: e3751a53-6e09-437d-9a82-d5370cea9121
async def check_record(
    record: Mapping[str, Any], catalog_id: str
) -> tuple[RecordVerdict, int]:
    """Judge ``record`` against the record catalog ``catalog_id`` (ADR-173).
    Returns the verdict and the number of rules. Stores nothing."""
    rules = load_record_catalog(resolve_record_catalog(catalog_id))
    return await evaluate(record, rules), len(rules)
