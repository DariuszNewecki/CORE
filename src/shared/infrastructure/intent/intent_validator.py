# src/shared/infrastructure/intent/intent_validator.py

"""Provides functionality for the intent_validator module."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft7Validator

from shared.infrastructure.intent.errors import GovernanceError
from shared.logger import getLogger


logger = getLogger(__name__)


_BOOTSTRAP_REQUIRED_FILES = (
    "META/intent_tree.schema.json",
    "META/rule_document.schema.json",
    "META/enums.json",
)


@dataclass(frozen=True)
# ID: 180eb0dc-ca56-45fd-a012-85df2d796891
class ValidationReport:
    schemas_loaded: int
    documents_validated: int
    errors: list[str]
    warnings: list[str]


# ID: 1b6b0b6c-6e63-4c39-8b2f-7a7d3c7b9b52
def validate_intent_tree(intent_root: Path, *, strict: bool = True) -> ValidationReport:
    """
    Strict, deterministic validation for the .intent tree.

    Bootstrap Contract v0 (mandatory in strict mode):
      - .intent/ exists and is a directory
      - .intent/META/ exists and is a directory
      - .intent/META/intent_tree.schema.json exists
      - .intent/META/rule_document.schema.json exists
      - .intent/META/enums.json exists

    Document validation rule (BigBoy pattern):
      - Every non-META JSON document MUST declare which schema governs it via '$schema'.
        Example for rule documents:
          "$schema": "META/rule_document.schema.json"

    No inference by directory/path is allowed. No heuristics. No silent fallbacks.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # -------------------------
    # Phase 0: filesystem gate
    # -------------------------
    if not intent_root.exists() or not intent_root.is_dir():
        msg = f".intent root does not exist or is not a directory: {intent_root}"
        if strict:
            raise GovernanceError(msg)
        errors.append(msg)
        return ValidationReport(0, 0, errors, warnings)

    meta_root = intent_root / "META"
    if not meta_root.exists() or not meta_root.is_dir():
        msg = f".intent/META does not exist or is not a directory: {meta_root}"
        if strict:
            raise GovernanceError(msg)
        errors.append(msg)
        return ValidationReport(0, 0, errors, warnings)

    # Exactly one META directory at root; no nested META allowed
    meta_dirs = [p for p in intent_root.iterdir() if p.is_dir() and p.name == "META"]
    if len(meta_dirs) != 1 or meta_dirs[0] != meta_root:
        msg = (
            f"Exactly one META directory is required at .intent/META "
            f"(found {len(meta_dirs)} at root)"
        )
        if strict:
            raise GovernanceError(msg)
        errors.append(msg)
        return ValidationReport(0, 0, errors, warnings)

    for p in intent_root.rglob("META"):
        if p != meta_root:
            msg = f"Nested META directory detected: {p}"
            if strict:
                raise GovernanceError(msg)
            errors.append(msg)
            return ValidationReport(0, 0, errors, warnings)

    # -------------------------
    # Phase 1: bootstrap gate
    # -------------------------
    missing = [
        rel for rel in _BOOTSTRAP_REQUIRED_FILES if not (intent_root / rel).exists()
    ]
    if missing:
        msg = (
            "Bootstrap Contract v0 violated. Missing required intent artifacts:\n"
            + "\n".join(f"- {m}" for m in missing)
        )
        if strict:
            raise GovernanceError(msg)
        errors.append(msg)
        return ValidationReport(0, 0, errors, warnings)

    intent_tree_schema_path = intent_root / "META/intent_tree.schema.json"
    rule_document_schema_path = intent_root / "META/rule_document.schema.json"

    intent_tree_schema = _load_json(intent_tree_schema_path)
    rule_document_schema = _load_json(rule_document_schema_path)

    _check_schema_is_valid(
        intent_tree_schema, intent_tree_schema_path, strict=strict, warnings=warnings
    )
    _check_schema_is_valid(
        rule_document_schema,
        rule_document_schema_path,
        strict=strict,
        warnings=warnings,
    )

    # For now, Bootstrap v0 defines at least one canonical schema for rule documents.
    # We can extend this later (still deterministically) by allowing additional schemas,
    # as long as documents explicitly declare them via '$schema'.
    schema_map: dict[str, dict[str, Any]] = {
        "META/rule_document.schema.json": rule_document_schema,
        "./META/rule_document.schema.json": rule_document_schema,
    }

    # -------------------------
    # Phase 2: validate documents
    # -------------------------
    documents_validated = 0

    for doc_path in intent_root.rglob("*.json"):
        if doc_path.is_relative_to(meta_root):
            continue
        if doc_path.name.endswith(".schema.json"):
            continue

        document = _load_json(doc_path)

        schema_ref = document.get("$schema")
        if not isinstance(schema_ref, str) or not schema_ref.strip():
            msg = (
                f"Document missing '$schema': {doc_path}\n"
                "CORE refuses to infer document type from path. "
                "Add an explicit schema reference, e.g.:\n"
                '  "$schema": "META/rule_document.schema.json"'
            )
            if strict:
                raise GovernanceError(msg)
            errors.append(msg)
            continue

        schema = schema_map.get(schema_ref.strip())
        if schema is None:
            msg = (
                f"Unknown '$schema' reference '{schema_ref}' in {doc_path}\n"
                "Allowed (Bootstrap v0):\n"
                + "\n".join(f"- {k}" for k in sorted(schema_map.keys()))
            )
            if strict:
                raise GovernanceError(msg)
            errors.append(msg)
            continue

        try:
            Draft7Validator(schema).validate(document)
        except jsonschema.ValidationError as e:
            msg = f"Schema validation failed for {doc_path}:\n{e.message}"
            if strict:
                raise GovernanceError(msg) from e
            errors.append(msg)
            continue

        documents_validated += 1

    logger.info(
        "Intent validation completed: %s documents validated", documents_validated
    )
    return ValidationReport(
        schemas_loaded=2,  # META schemas validated (intent_tree + rule_document)
        documents_validated=documents_validated,
        errors=errors,
        warnings=warnings,
    )


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text("utf-8")) or {}
    except Exception as e:
        raise GovernanceError(f"Failed to parse JSON: {path}: {e}") from e


def _check_schema_is_valid(
    schema: dict[str, Any],
    schema_path: Path,
    *,
    strict: bool,
    warnings: list[str],
) -> None:
    try:
        Draft7Validator.check_schema(schema)
    except Exception as e:
        msg = f"Invalid JSON Schema at {schema_path}: {e}"
        if strict:
            raise GovernanceError(msg) from e
        warnings.append(msg)
