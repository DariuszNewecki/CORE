# src/mind/governance/meta_validator.py
"""
Meta-Constitutional Validator.

Validates ALL .intent documents against GLOBAL-DOCUMENT-META-SCHEMA.yaml
and their respective JSON schemas via schema_id resolution.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate as json_validate

from shared.logger import getLogger
from shared.path_utils import get_repo_root


logger = getLogger(__name__)


@dataclass
# ID: 4b2799ff-a6fe-43b4-9993-74eac90423fc
class ValidationError:
    """A single validation error or warning."""

    document: str
    error_type: str
    message: str
    severity: str = "error"
    field: str | None = None


@dataclass
# ID: 27ecb7d7-df65-414b-a55a-9b7c1b5afad2
class ValidationReport:
    """Complete validation report for .intent documents."""

    valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationError]
    documents_checked: int
    documents_valid: int
    documents_invalid: int


# ID: db00c12f-fcf1-44cf-8a42-a806404216fb
class MetaValidator:
    """
    Validates .intent documents against GLOBAL-DOCUMENT-META-SCHEMA.

    Phase 1: Validates header structure
    Phase 2: Validates against JSON schemas via schema_id resolution
    """

    # ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
    def __init__(self, intent_root: Path | None = None):
        """
        Initialize validator with .intent root.

        Args:
            intent_root: Path to .intent directory, defaults to repo_root/.intent
        """
        self.intent_root = intent_root or get_repo_root() / ".intent"
        self.meta_schema = self._load_meta_schema()
        self.errors: list[ValidationError] = []
        self.warnings: list[ValidationError] = []
        self.schema_cache: dict[str, dict[str, Any]] = {}

    # ID: b2c3d4e5-f678-90ab-cdef-123456789012
    def _load_meta_schema(self) -> dict[str, Any]:
        """
        Load GLOBAL-DOCUMENT-META-SCHEMA.yaml.

        Returns:
            Loaded meta-schema dictionary

        Raises:
            FileNotFoundError: If META-SCHEMA not found
        """
        meta_path = (
            self.intent_root / "charter/constitution/GLOBAL-DOCUMENT-META-SCHEMA.yaml"
        )
        if not meta_path.exists():
            raise FileNotFoundError(f"META-SCHEMA not found: {meta_path}")

        with open(meta_path) as f:
            schema = yaml.safe_load(f)

        logger.info(f"Loaded GLOBAL-DOCUMENT-META-SCHEMA v{schema.get('version')}")
        return schema

    # ID: c3d4e5f6-7890-abcd-ef12-34567890abcd
    def validate_all_documents(self) -> ValidationReport:
        """
        Scan and validate all .intent YAML documents.

        Returns:
            ValidationReport with results
        """
        self.errors.clear()
        self.warnings.clear()
        self.schema_cache.clear()

        scope = self.meta_schema["scope"]
        excludes = [p.replace(".intent/", "") for p in scope["excludes"]]

        documents_checked = 0
        documents_valid = 0
        documents_invalid = 0

        # Find all YAML files
        for yaml_file in self.intent_root.rglob("*.yaml"):
            rel_path = yaml_file.relative_to(self.intent_root)

            # Check exclusions
            if any(str(rel_path).startswith(ex) for ex in excludes):
                logger.debug("Skipping excluded: %s", rel_path)
                continue

            documents_checked += 1
            is_valid = self._validate_document(yaml_file, rel_path)

            if is_valid:
                documents_valid += 1
            else:
                documents_invalid += 1

        # Also check .yml files
        for yml_file in self.intent_root.rglob("*.yml"):
            rel_path = yml_file.relative_to(self.intent_root)

            if any(str(rel_path).startswith(ex) for ex in excludes):
                continue

            documents_checked += 1
            is_valid = self._validate_document(yml_file, rel_path)

            if is_valid:
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

    # ID: d4e5f678-90ab-cdef-1234-567890abcdef
    def _validate_document(self, doc_path: Path, rel_path: Path) -> bool:
        """
        Validate single document.

        Args:
            doc_path: Absolute path to document
            rel_path: Relative path from .intent root

        Returns:
            True if valid, False otherwise
        """
        doc_errors_before = len(self.errors)

        # Load document
        try:
            with open(doc_path) as f:
                doc = yaml.safe_load(f)
        except Exception as e:
            self._add_error(
                document=str(rel_path),
                error_type="parse_error",
                message=f"Failed to parse YAML: {e}",
            )
            return False

        if not isinstance(doc, dict):
            self._add_error(
                document=str(rel_path),
                error_type="invalid_structure",
                message="Document must be a YAML dictionary",
            )
            return False

        # Validate required header fields
        self._validate_required_fields(str(rel_path), doc)

        # Validate field constraints
        self._validate_field_constraints(str(rel_path), doc)

        # Validate against JSON schema (Phase 2)
        self._validate_against_json_schema(str(rel_path), doc)

        # Check if new errors were added
        return len(self.errors) == doc_errors_before

    # ID: e5f67890-abcd-ef12-3456-7890abcdef12
    def _validate_required_fields(self, doc_name: str, doc: dict):
        """
        Validate all required header fields are present.

        Args:
            doc_name: Document name for error reporting
            doc: Document dictionary
        """
        required = self.meta_schema["header_schema"]["required_fields"]

        for field in required:
            if field not in doc:
                self._add_error(
                    document=doc_name,
                    error_type="missing_required_field",
                    message=f"Missing required field: {field}",
                    field=field,
                )

    # ID: f6789abc-def1-2345-6789-0abcdef12345
    def _validate_field_constraints(self, doc_name: str, doc: dict):
        """
        Validate field patterns and constraints.

        Args:
            doc_name: Document name for error reporting
            doc: Document dictionary
        """
        fields = self.meta_schema["header_schema"]["fields"]

        # Validate id pattern
        if "id" in doc:
            pattern = fields["id"]["pattern"]
            if not re.match(pattern, doc["id"]):
                self._add_error(
                    document=doc_name,
                    error_type="invalid_pattern",
                    message=f"id '{doc['id']}' does not match pattern {pattern}",
                    field="id",
                )

        # Validate version pattern
        if "version" in doc:
            pattern = fields["version"]["pattern"]
            if not re.match(pattern, doc["version"]):
                self._add_error(
                    document=doc_name,
                    error_type="invalid_pattern",
                    message=f"version '{doc['version']}' does not match pattern {pattern}",
                    field="version",
                )

        # Validate status enum
        if "status" in doc:
            allowed = fields["status"]["allowed_values"]
            if doc["status"] not in allowed:
                self._add_error(
                    document=doc_name,
                    error_type="invalid_value",
                    message=f"status '{doc['status']}' not in allowed values: {allowed}",
                    field="status",
                )

        # Validate type pattern
        if "type" in doc:
            pattern = fields["type"]["pattern"]
            if not re.match(pattern, doc["type"]):
                self._add_error(
                    document=doc_name,
                    error_type="invalid_pattern",
                    message=f"type '{doc['type']}' does not match pattern {pattern}",
                    field="type",
                )

        # Validate owners structure
        if "owners" in doc:
            if not isinstance(doc["owners"], dict):
                self._add_error(
                    document=doc_name,
                    error_type="invalid_structure",
                    message="owners must be a dictionary",
                    field="owners",
                )
            elif "accountable" not in doc["owners"]:
                self._add_error(
                    document=doc_name,
                    error_type="missing_required_field",
                    message="owners.accountable is required",
                    field="owners.accountable",
                )

        # Validate review structure
        if "review" in doc:
            if not isinstance(doc["review"], dict):
                self._add_error(
                    document=doc_name,
                    error_type="invalid_structure",
                    message="review must be a dictionary",
                    field="review",
                )
            elif "frequency" not in doc["review"]:
                self._add_error(
                    document=doc_name,
                    error_type="missing_required_field",
                    message="review.frequency is required",
                    field="review.frequency",
                )

        # Validate schema_id pattern
        if "schema_id" in doc:
            pattern = fields["schema_id"]["pattern"]
            if not re.match(pattern, doc["schema_id"]):
                self._add_error(
                    document=doc_name,
                    error_type="invalid_pattern",
                    message=f"schema_id '{doc['schema_id']}' does not match pattern {pattern}",
                    field="schema_id",
                )

    # ID: 789abcde-f012-3456-789a-bcdef0123456
    def _resolve_schema(self, schema_id: str) -> dict[str, Any] | None:
        """
        Resolve JSON schema by schema_id.

        Args:
            schema_id: Schema identifier to resolve

        Returns:
            Schema dictionary if found, None otherwise
        """
        # Check cache first
        if schema_id in self.schema_cache:
            return self.schema_cache[schema_id]

        schemas_root = self.intent_root / "charter/schemas"

        # Search all .schema.json files
        for schema_file in schemas_root.rglob("*.schema.json"):
            try:
                with open(schema_file) as f:
                    schema = json.load(f)

                # Match on internal schema_id field
                if schema.get("schema_id") == schema_id:
                    logger.debug(
                        f"Resolved {schema_id} -> {schema_file.relative_to(self.intent_root)}"
                    )
                    self.schema_cache[schema_id] = schema
                    return schema
            except Exception as e:
                logger.warning("Failed to load schema {schema_file}: %s", e)
                continue

        return None

    # ID: 89abcdef-0123-4567-89ab-cdef01234567
    def _validate_against_json_schema(self, doc_name: str, doc: dict):
        """
        Validate document against its JSON schema.

        Args:
            doc_name: Document name for error reporting
            doc: Document dictionary
        """
        if "schema_id" not in doc:
            return  # Already caught by required fields check

        schema_id = doc["schema_id"]
        schema = self._resolve_schema(schema_id)

        if schema is None:
            # Only warn, not error - allows gradual schema rollout
            self._add_error(
                document=doc_name,
                error_type="schema_not_found",
                message=f"No JSON schema found for schema_id: {schema_id}",
                field="schema_id",
                severity="warning",
            )
            return

        # Validate against JSON schema
        try:
            json_validate(instance=doc, schema=schema)
            logger.debug("Document {doc_name} validated against %s", schema_id)
        except JsonSchemaValidationError as e:
            # Extract meaningful error info
            error_path = ".".join(str(p) for p in e.path) if e.path else "root"
            self._add_error(
                document=doc_name,
                error_type="schema_validation_failed",
                message=f"JSON schema validation failed at {error_path}: {e.message}",
                field=error_path if error_path != "root" else None,
            )

    # ID: 67890abc-def1-2345-6789-0abcdef12345
    def _add_error(
        self,
        document: str,
        error_type: str,
        message: str,
        field: str | None = None,
        severity: str = "error",
    ):
        """
        Add validation error.

        Args:
            document: Document path
            error_type: Error type identifier
            message: Human-readable error message
            field: Optional field name
            severity: "error" or "warning"
        """
        error = ValidationError(
            document=document,
            error_type=error_type,
            message=message,
            field=field,
            severity=severity,
        )

        if severity == "error":
            self.errors.append(error)
        else:
            self.warnings.append(error)
