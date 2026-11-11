# src/body/services/grc/catalog_contract.py
"""The catalog contract (ADR-174), in warn mode for CORE 3.x.

Checks a GRC catalog tree against the format schemas in ``.intent/META/``
(``catalog.schema.json``, ``catalog_provenance.schema.json``,
``catalog_inventory.schema.json``) and the engine registry. Every check
returns warnings and never refuses: a catalog that only draws warnings still
loads, as before. In CORE 4.0 each of these warnings becomes a refusal.

Rules (ADR-174):

- D1: a ``catalog.yaml``, ``provenance.yaml`` or ``inventory.yaml`` has no
  ``format_version``.
- D3: such a file fails its format schema in any other way.
- D4: a catalog has no ``provenance.yaml`` beside it.
- D7: a ``catalog.yaml`` sits under ``internal/``. It is still not loaded
  (``catalog_resolver``, #1336); the warning says it is ignored.
- D8: a requirement names an engine id the engine registry does not know.

Read-only: reads YAML and JSON, writes nothing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shared.logger import getLogger


logger = getLogger(__name__)

_REFUSAL_NOTE = "this becomes a refusal in CORE 4.0"
_SCHEMAS = {
    "catalog": "catalog.schema.json",
    "provenance": "catalog_provenance.schema.json",
    "inventory": "catalog_inventory.schema.json",
}
_INTERNAL_TIER = "internal"
_CATALOG_FILENAME = "catalog.yaml"
_PROVENANCE_FILENAME = "provenance.yaml"
_INVENTORY_FILENAME = "inventory.yaml"

# Warnings already logged in this process: a catalog is loaded many times
# per run, and one line per (catalog, rule, message) is enough.
_logged: set[tuple[str, str, str]] = set()


@dataclass(frozen=True)
# ID: 2d7a9c4e-1b8f-4e6a-9d3c-5f0b7e2a8c16
class CatalogContractWarning:
    """One breach of the catalog contract: which catalog, which rule, what."""

    catalog: str
    rule_id: str
    message: str

    def __str__(self) -> str:
        return f"catalog {self.catalog}: {self.rule_id} {self.message}; {_REFUSAL_NOTE}"


# ID: 8f3b1d6e-4a2c-4c9e-b7d5-1e9a6c3f2b84
def check_catalog(path: Path) -> list[CatalogContractWarning]:
    """Contract warnings for one ``catalog.yaml`` and its ``provenance.yaml``.

    Covers D1, D3 and D8 for the catalog file, and D4, D1 and D3 for its
    provenance. ``path`` is the ``catalog.yaml``; the catalog is named by its
    directory (the framework id).
    """
    name = path.parent.name
    warnings: list[CatalogContractWarning] = []
    data = _read_yaml(path)
    if data is None:
        return [
            CatalogContractWarning(
                name, "ADR-174 D3", f"{path.name} is not readable YAML"
            )
        ]
    warnings += _schema_warnings(name, path.name, data, "catalog")
    warnings += _engine_warnings(name, data)

    provenance = path.parent / _PROVENANCE_FILENAME
    if not provenance.is_file():
        warnings.append(
            CatalogContractWarning(
                name, "ADR-174 D4", f"has no {_PROVENANCE_FILENAME} beside {path.name}"
            )
        )
    else:
        prov_data = _read_yaml(provenance)
        if prov_data is None:
            warnings.append(
                CatalogContractWarning(
                    name, "ADR-174 D3", f"{_PROVENANCE_FILENAME} is not readable YAML"
                )
            )
        else:
            warnings += _schema_warnings(
                name, _PROVENANCE_FILENAME, prov_data, "provenance"
            )
    return warnings


# ID: 5c1e8a3f-7d2b-4f9a-8e6c-3b0d9f4a7e25
def check_catalog_root(root: Path) -> list[CatalogContractWarning]:
    """Contract warnings for the catalog root: ``inventory.yaml`` (D1, D3) and
    any ``catalog.yaml`` placed under ``internal/`` (D7)."""
    warnings: list[CatalogContractWarning] = []
    label = f"root {root.name}"
    inventory = root / _INVENTORY_FILENAME
    if inventory.is_file():
        data = _read_yaml(inventory)
        if data is None:
            warnings.append(
                CatalogContractWarning(
                    label,
                    "ADR-174 D3",
                    f"{_INVENTORY_FILENAME} is not readable YAML",
                )
            )
        else:
            warnings += _schema_warnings(label, _INVENTORY_FILENAME, data, "inventory")
    for path in sorted((root / _INTERNAL_TIER).glob(f"*/{_CATALOG_FILENAME}")):
        warnings.append(
            CatalogContractWarning(
                path.parent.name,
                "ADR-174 D7",
                f"{_CATALOG_FILENAME} under {_INTERNAL_TIER}/ is not a catalog "
                "and is ignored",
            )
        )
    return warnings


# ID: 9a6d4b2e-3f1c-4a8e-b5d7-2c8f0e6a1b39
def log_warnings(warnings: list[CatalogContractWarning]) -> None:
    """Log each warning once per process."""
    for warning in warnings:
        key = (warning.catalog, warning.rule_id, warning.message)
        if key in _logged:
            continue
        _logged.add(key)
        logger.warning("Catalog contract: %s", warning)


def _read_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return None


def _schema_warnings(
    name: str, filename: str, data: Any, kind: str
) -> list[CatalogContractWarning]:
    warnings: list[CatalogContractWarning] = []
    missing_version = isinstance(data, dict) and "format_version" not in data
    if missing_version:
        warnings.append(
            CatalogContractWarning(
                name, "ADR-174 D1", f"{filename} has no format_version"
            )
        )
    validator = _validator(kind)
    if validator is None:
        return warnings
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        if (
            missing_version
            and error.validator == "required"
            and not error.absolute_path
            and "'format_version'" in error.message
        ):
            continue  # already reported as D1
        where = "/".join(str(p) for p in error.absolute_path) or "<root>"
        warnings.append(
            CatalogContractWarning(
                name,
                "ADR-174 D3",
                f"{filename} fails {_SCHEMAS[kind]} at {where}: {error.message}",
            )
        )
    return warnings


def _engine_warnings(name: str, data: Any) -> list[CatalogContractWarning]:
    requirements = data.get("requirements") if isinstance(data, dict) else None
    if not isinstance(requirements, list):
        return []
    from mind.governance.rule_executor import known_engine_ids

    known = known_engine_ids()
    warnings = []
    for entry in requirements:
        if not isinstance(entry, dict):
            continue
        engine = entry.get("engine")
        if isinstance(engine, str) and engine not in known:
            warnings.append(
                CatalogContractWarning(
                    name,
                    "ADR-174 D8",
                    f"requirement {entry.get('id')!r} names unknown engine {engine!r}",
                )
            )
    return warnings


_validators: dict[str, Any] = {}


def _validator(kind: str) -> Any:
    """The JSON-schema validator for ``kind``, or None when the schema is not
    found (logged once): the contract then checks only for format_version."""
    if kind in _validators:
        return _validators[kind]
    from jsonschema.validators import validator_for

    schema = _load_schema(_SCHEMAS[kind])
    if schema is None:
        logger.warning(
            "Catalog contract: %s not found in .intent/META or the bundled "
            "floor; schema checks for %s files are skipped",
            _SCHEMAS[kind],
            kind,
        )
        _validators[kind] = None
        return None
    _validators[kind] = validator_for(schema)(schema)
    return _validators[kind]


def _load_schema(filename: str) -> dict[str, Any] | None:
    """Read a META schema from the active ``.intent/`` root, else from the
    machinery floor shipped in the wheel (an install whose ``.intent/`` predates
    the schema)."""
    candidates: list[Path] = []
    try:
        from shared.infrastructure.intent.intent_repository import (
            get_intent_repository,
        )

        candidates.append(get_intent_repository().root / "META" / filename)
    except Exception as exc:
        logger.debug("Catalog contract: no intent repository (%s)", exc)
    try:
        import importlib.resources

        floor = Path(str(importlib.resources.files("shared._machinery_floor")))
        candidates.append(floor / "META" / filename)
    except Exception as exc:
        logger.debug("Catalog contract: no machinery floor (%s)", exc)
    for candidate in candidates:
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))
    return None
