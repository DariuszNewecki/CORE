# src/body/services/intent_schema_validator.py

"""
Intent Schema Validator - Constitutional Document Validation

CONSTITUTIONAL ALIGNMENT:
- Single Responsibility: Validate .intent documents against JSON schemas
- No CLI dependencies (pure business logic)
- Reusable across CLI, API, automation

Extracted from cli/logic/validate.py to separate validation logic from presentation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from jsonschema import ValidationError, validate

from shared.config_loader import load_yaml_file
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 1613fe5a-7770-4dc8-ad69-aede3325eb35
# ID: 4d233a8d-dfcc-4b90-acac-d65515d83159
@dataclass
# ID: a3d80ab0-1305-4aa5-ad7d-e33f55cad6fd
class SchemaValidationResult:
    """Result of validating a document against its schema."""

    yaml_path: Path
    schema_path: Path
    is_valid: bool
    error_message: str | None = None


# ID: 0cfd46f7-a6fc-447f-a941-313e1be66356
# ID: 903dd29d-e370-4441-8489-668935704ab9
@dataclass
# ID: f90b4c8b-4698-4836-b1aa-056515fd6ca4
class SchemaPair:
    """A document paired with its schema."""

    yaml_path: Path
    schema_path: Path


# ID: 79ef644b-8b3e-4ff0-967d-8619926424b3
# ID: 8cbe3ca9-3b16-4d69-8608-8b55c422e500
class IntentSchemaValidator:
    """
    Validates .intent YAML documents against their declared JSON schemas.

    Usage:
        validator = IntentSchemaValidator(Path(".intent"))
        results = validator.validate_all()
    """

    def __init__(self, intent_root: Path):
        """
        Initialize validator.

        Args:
            intent_root: Path to .intent directory
        """
        self.intent_root = intent_root.resolve()
        self._exclude_prefixes = ("runtime/", "mind_export/", "keys/")

    # -------------------------
    # Core Validation Logic
    # -------------------------

    # ID: f416b69b-54a9-4468-b37e-168e87a0a3a7
    # ID: 5443f768-20c3-4d05-9a7d-9df34e1b61e0
    def validate_pair(self, pair: SchemaPair) -> SchemaValidationResult:
        """
        Validate a single YAML document against its schema.

        Args:
            pair: Document and schema pair

        Returns:
            Validation result
        """
        if not pair.yaml_path.exists():
            return SchemaValidationResult(
                yaml_path=pair.yaml_path,
                schema_path=pair.schema_path,
                is_valid=False,
                error_message=f"Missing file: {pair.yaml_path}",
            )

        if not pair.schema_path.exists():
            return SchemaValidationResult(
                yaml_path=pair.yaml_path,
                schema_path=pair.schema_path,
                is_valid=False,
                error_message=f"Missing schema: {pair.schema_path}",
            )

        try:
            data = load_yaml_file(pair.yaml_path)
            schema = self._load_json(pair.schema_path)
            validate(instance=data, schema=schema)

            return SchemaValidationResult(
                yaml_path=pair.yaml_path,
                schema_path=pair.schema_path,
                is_valid=True,
            )
        except ValidationError as e:
            path = ".".join(map(str, e.path)) or "(root)"
            return SchemaValidationResult(
                yaml_path=pair.yaml_path,
                schema_path=pair.schema_path,
                is_valid=False,
                error_message=f"{e.message} at {path}",
            )
        except Exception as e:
            return SchemaValidationResult(
                yaml_path=pair.yaml_path,
                schema_path=pair.schema_path,
                is_valid=False,
                error_message=f"Unexpected validation error: {e!r}",
            )

    # ID: 12009828-76ab-420f-ac19-b7e5c4a22dcc
    # ID: 236186ba-1470-4cf7-8efb-ab9db910bb76
    def validate_all(self) -> tuple[list[SchemaValidationResult], list[str]]:
        """
        Validate all .intent documents that declare $schema.

        Returns:
            (results, skipped_messages)
        """
        pairs, skipped = self._discover_schema_pairs()
        results = [self.validate_pair(pair) for pair in pairs]
        return results, skipped

    # -------------------------
    # Discovery Logic
    # -------------------------

    # ID: 962c3ea3-c187-457c-91e1-d7de2b594b60
    # ID: 5e6a6d73-f710-48f4-91af-b37a0ca67bd5
    def _discover_schema_pairs(self) -> tuple[list[SchemaPair], list[str]]:
        """
        Discover YAML → JSON-schema pairs using the `$schema` field.

        Returns:
            (pairs, skipped_messages)
        """
        pairs: list[SchemaPair] = []
        skipped: list[str] = []

        for yaml_path in self._iter_intent_yaml():
            rel = yaml_path.relative_to(self.intent_root).as_posix()

            try:
                data = load_yaml_file(yaml_path)
            except Exception as exc:
                skipped.append(f"[SKIP] {rel}: YAML parse error: {exc!r}")
                continue

            if not isinstance(data, dict):
                skipped.append(f"[SKIP] {rel}: top-level YAML is not a mapping")
                continue

            schema_ref = data.get("$schema")
            if not schema_ref:
                skipped.append(f"[SKIP] {rel}: no $schema field; not validated")
                continue

            schema_path = (self.intent_root / schema_ref).resolve()
            pairs.append(SchemaPair(yaml_path=yaml_path, schema_path=schema_path))

        return pairs, skipped

    # ID: 6bc9e6f4-dd2e-4bcd-b2f8-caf7df9bc1d0
    # ID: 365ba3bf-4559-4300-8536-e88995c9a427
    def _iter_intent_yaml(self) -> list[Path]:
        """
        Return all YAML/YML files under .intent, excluding state folders.

        Returns:
            Sorted list of YAML file paths
        """
        if not self.intent_root.exists():
            logger.error("Intent root %s does not exist", self.intent_root)
            return []

        files: list[Path] = []
        seen: set[Path] = set()

        for pattern in ("**/*.yaml", "**/*.yml"):
            for path in self.intent_root.glob(pattern):
                if path in seen:
                    continue
                rel = path.relative_to(self.intent_root).as_posix()
                if any(rel.startswith(prefix) for prefix in self._exclude_prefixes):
                    continue
                seen.add(path)
                files.append(path)

        return sorted(files)

    # -------------------------
    # Utilities
    # -------------------------

    @staticmethod
    def _load_json(path: Path) -> dict:
        """Load JSON schema from file."""
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
