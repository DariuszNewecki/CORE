# src/mind/governance/meta_validator.py
"""
Meta-Constitutional Validator.

Validates ALL .intent documents against GLOBAL-DOCUMENT-META-SCHEMA.json
and their respective JSON schemas via schema_id resolution.

FIX: Implements a Schema Registry to resolve internal $ref links.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema.validators import validator_for

from shared.infrastructure.intent.intent_repository import (
    get_intent_repository,
)
from shared.logger import getLogger


logger = getLogger(__name__)


@dataclass
# ID: 840ed0a8-4180-495a-96b2-facc9837557c
class ValidationError:
    document: str
    error_type: str
    message: str
    severity: str = "error"
    field: str | None = None


@dataclass
# ID: 64d145aa-3edc-40dd-8aba-e83f56177406
class ValidationReport:
    valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationError]
    documents_checked: int
    documents_valid: int
    documents_invalid: int


# ID: 6c47ddbc-3670-441c-ab73-04d97830b6b2
class MetaValidator:
    def __init__(self, intent_root: Path | None = None):
        self.repo = get_intent_repository()
        self.intent_root = self.repo.root

        # 1. Build a local cache of all schemas to resolve $ref issues
        self._all_schemas: dict[str, dict[str, Any]] = self._index_all_schemas()

        self.meta_schema = self._load_meta_schema()
        self.errors: list[ValidationError] = []
        self.warnings: list[ValidationError] = []

    def _index_all_schemas(self) -> dict[str, dict[str, Any]]:
        """Finds every .schema.json in the system and stores it in memory."""
        index = {}
        # Search the entire schemas directory
        schemas_path = self.intent_root / "schemas"
        for schema_file in schemas_path.rglob("*.schema.json"):
            try:
                # Use filename as the lookup key for $ref resolution
                doc = self.repo.load_document(schema_file)
                index[schema_file.name] = doc
                # Also index by the internal schema_id if present
                if "schema_id" in doc:
                    index[doc["schema_id"]] = doc
            except Exception:
                continue
        return index

    def _load_meta_schema(self) -> dict[str, Any]:
        rel_path = "schemas/META/GLOBAL-DOCUMENT-META-SCHEMA.json"
        try:
            abs_path = self.repo.resolve_rel(rel_path)
            return self.repo.load_document(abs_path)
        except Exception as e:
            raise FileNotFoundError(f"META-SCHEMA not found: {rel_path}. Error: {e}")

    # ID: a3e2e7c8-7f90-4dd1-9f6e-ab126d72f331
    def validate_all_documents(self) -> ValidationReport:
        self.errors.clear()
        self.warnings.clear()

        scope = self.meta_schema.get("scope", {})
        excludes = [p.replace(".intent/", "") for p in scope.get("excludes", [])]

        documents_checked = 0
        documents_valid = 0
        documents_invalid = 0

        for ext in ("*.yaml", "*.yml", "*.json"):
            for doc_file in self.intent_root.rglob(ext):
                # Skip the schemas themselves and excluded paths
                if "/schemas/" in str(doc_file).replace("\\", "/"):
                    continue

                rel_path = doc_file.relative_to(self.intent_root)
                if any(str(rel_path).startswith(ex) for ex in excludes):
                    continue

                documents_checked += 1
                if self._validate_document(doc_file, rel_path):
                    documents_valid += 1
                else:
                    documents_invalid += 1

        return ValidationReport(
            valid=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings,
            documents_checked=documents_checked,
            documents_valid=documents_valid,
            documents_invalid=documents_invalid,
        )

    def _validate_document(self, doc_path: Path, rel_path: Path) -> bool:
        doc_errors_before = len(self.errors)
        try:
            doc = self.repo.load_document(doc_path)
        except Exception as e:
            self._add_error(str(rel_path), "parse_error", f"Load failed: {e}")
            return False

        if not isinstance(doc, dict):
            self._add_error(str(rel_path), "invalid_structure", "Must be a mapping")
            return False

        self._validate_required_fields(str(rel_path), doc)
        self._validate_field_constraints(str(rel_path), doc)
        self._validate_against_json_schema(str(rel_path), doc)

        return len(self.errors) == doc_errors_before

    def _validate_required_fields(self, doc_name: str, doc: dict):
        required = self.meta_schema["header_schema"]["required_fields"]
        for field in required:
            if field not in doc:
                self._add_error(
                    doc_name, "missing_field", f"Missing field: {field}", field
                )

    def _validate_field_constraints(self, doc_name: str, doc: dict):
        fields = self.meta_schema["header_schema"]["fields"]
        for field_name in ["id", "version", "type", "schema_id"]:
            if field_name in doc and field_name in fields:
                pattern = fields[field_name].get("pattern")
                if pattern and not re.match(pattern, str(doc[field_name])):
                    self._add_error(
                        doc_name, "invalid_pattern", f"{field_name} invalid", field_name
                    )

    def _validate_against_json_schema(self, doc_name: str, doc: dict):
        schema_id = doc.get("schema_id")
        if not schema_id:
            return

        schema = self._all_schemas.get(schema_id)
        if not schema:
            self._add_error(
                doc_name,
                "schema_not_found",
                f"No schema for: {schema_id}",
                "schema_id",
                "warning",
            )
            return

        try:
            # FIX: Create a validator that knows about all our local schemas
            validator_cls = validator_for(schema)

            # Simple resolver that pulls from our in-memory index
            # This is the "Sound Solution" for local $ref issues
            # ID: ac52e1ca-d781-4664-ac7f-833bafcb384b
            def retrieve_schema(uri):
                name = uri.split("/")[-1]
                if name in self._all_schemas:
                    return self._all_schemas[name]
                raise Exception(f"Could not resolve {uri}")

            # Run validation with a custom resolver logic (simplified for 3.12 compatibility)
            from jsonschema import RefResolver

            resolver = RefResolver.from_schema(schema, store=self._all_schemas)
            validator = validator_cls(schema, resolver=resolver)

            for error in validator.iter_errors(doc):
                path = ".".join(map(str, error.path)) or "root"
                self._add_error(doc_name, "schema_violation", error.message, path)

        except Exception as e:
            self._add_error(
                doc_name, "validator_error", f"Internal validator error: {e}"
            )

    def _add_error(
        self,
        document: str,
        error_type: str,
        message: str,
        field: str | None = None,
        severity: str = "error",
    ):
        error = ValidationError(document, error_type, message, severity, field)
        if severity == "error":
            self.errors.append(error)
        else:
            self.warnings.append(error)
