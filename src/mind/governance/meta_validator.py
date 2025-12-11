# src/mind/governance/meta_validator.py
"""
Meta-Constitutional Validator.

Validates that all constitutional documents follow the canonical schema defined
in META-SCHEMA.yaml. All validation rules are loaded dynamically from the schema
rather than being hard-coded.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shared.logger import getLogger


logger = getLogger(__name__)


@dataclass
# ID: 84f33759-1121-4d2f-817b-f95084f1fde4
class ValidationError:
    """A single validation error or warning."""

    document: str
    principle_id: str | None
    error_type: str
    message: str
    severity: str


@dataclass
# ID: 83d9098a-55b6-401c-8090-1cf3cfad3152
class ValidationReport:
    """Complete validation report for constitution."""

    valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationError]
    documents_checked: int
    principles_validated: int


# ID: 45ef1a23-323e-4d2d-9c41-94534ddac330
class MetaValidator:
    """
    Validates constitutional documents against META-SCHEMA.

    All validation rules are loaded from META-SCHEMA.yaml to ensure
    the validator itself respects constitutional supremacy.
    """

    def __init__(self, constitution_path: Path = Path(".intent/charter/constitution")):
        """
        Initialize meta-validator.

        Args:
            constitution_path: Path to constitution directory
        """
        self.constitution_path = constitution_path
        self.meta_schema = self._load_meta_schema()
        self.errors: list[ValidationError] = []
        self.warnings: list[ValidationError] = []
        self.documents_checked = 0
        self.principles_validated = 0

    def _load_meta_schema(self) -> dict:
        """Load META-SCHEMA.yaml as source of truth."""
        meta_file = self.constitution_path / "META-SCHEMA.yaml"
        if not meta_file.exists():
            raise FileNotFoundError(f"META-SCHEMA.yaml not found at {meta_file}")

        schema = yaml.safe_load(meta_file.read_text())
        logger.info(f"📋 Loaded META-SCHEMA v{schema.get('version', 'unknown')}")
        return schema

    @property
    # ID: 10638e03-f1c4-4851-9187-55a5ca3ff86a
    def required_document_fields(self) -> set[str]:
        """Extract required fields from META-SCHEMA."""
        fields = self.meta_schema["canonical_document_structure"]
        return set(fields["required_fields"])

    @property
    # ID: 993beda8-d7b7-40ac-a165-1225c196384b
    def optional_document_fields(self) -> set[str]:
        """Extract optional fields from META-SCHEMA."""
        fields = self.meta_schema["canonical_document_structure"]
        return set(fields["optional_fields"])

    @property
    # ID: 480ae02f-c580-4d82-a912-9493752bb742
    def max_nesting_depth(self) -> int:
        """Extract max nesting depth from META-SCHEMA."""
        structure = self.meta_schema["canonical_document_structure"]
        return structure["max_nesting_depth"]

    # ID: 57411273-37db-4a7a-80ac-6872d01d6594
    def validate_constitution(self) -> ValidationReport:
        """
        Validate all constitutional documents.

        Returns:
            ValidationReport with status and errors/warnings
        """
        logger.info("🔍 Validating constitutional structure...")

        self.errors.clear()
        self.warnings.clear()
        self.documents_checked = 0
        self.principles_validated = 0

        yaml_files = list(self.constitution_path.glob("*.yaml"))

        for yaml_file in yaml_files:
            if "META" in yaml_file.name.upper():
                continue

            self._validate_document(yaml_file)
            self.documents_checked += 1

        valid = len(self.errors) == 0

        return ValidationReport(
            valid=valid,
            errors=self.errors,
            warnings=self.warnings,
            documents_checked=self.documents_checked,
            principles_validated=self.principles_validated,
        )

    def _validate_document(self, yaml_file: Path):
        """Validate a single constitutional document."""
        try:
            content = yaml.safe_load(yaml_file.read_text())
        except Exception as e:
            self._add_error(
                document=yaml_file.name,
                error_type="parse_error",
                message=f"Failed to parse YAML: {e}",
            )
            return

        self._validate_document_fields(yaml_file.name, content)

        if "principles" in content:
            self._validate_principles(yaml_file.name, content["principles"])

        self._validate_nesting_depth(yaml_file.name, content)

    def _validate_document_fields(self, doc_name: str, content: dict):
        """Validate required document fields."""
        if not isinstance(content, dict):
            self._add_error(
                document=doc_name,
                error_type="invalid_structure",
                message="Document must be a YAML dictionary",
            )
            return

        missing = self.required_document_fields - set(content.keys())
        if missing:
            self._add_error(
                document=doc_name,
                error_type="missing_fields",
                message=f"Missing required fields: {missing}",
            )

    def _validate_principles(self, doc_name: str, principles: dict):
        """Validate all principles in document."""
        if not isinstance(principles, dict):
            self._add_error(
                document=doc_name,
                error_type="invalid_principles",
                message="principles must be a dictionary",
            )
            return

        for principle_id, principle_data in principles.items():
            self._validate_principle(doc_name, principle_id, principle_data)
            self.principles_validated += 1

    def _validate_principle(self, doc_name: str, principle_id: str, data: dict):
        """Validate a single principle."""
        if not isinstance(data, dict):
            self._add_error(
                document=doc_name,
                principle_id=principle_id,
                error_type="invalid_principle_structure",
                message="Principle must be a dictionary",
            )

    def _validate_nesting_depth(
        self, doc_name: str, content: Any, current_depth: int = 0
    ):
        """Validate maximum nesting depth."""
        if current_depth > self.max_nesting_depth:
            self._add_error(
                document=doc_name,
                error_type="excessive_nesting",
                message=f"Nesting depth exceeds maximum of {self.max_nesting_depth}",
            )
            return

        if isinstance(content, dict):
            for value in content.values():
                self._validate_nesting_depth(doc_name, value, current_depth + 1)
        elif isinstance(content, list):
            for item in content:
                self._validate_nesting_depth(doc_name, item, current_depth)

    def _add_error(
        self,
        document: str,
        error_type: str,
        message: str,
        principle_id: str | None = None,
    ):
        """Add a validation error."""
        self.errors.append(
            ValidationError(
                document=document,
                principle_id=principle_id,
                error_type=error_type,
                message=message,
                severity="error",
            )
        )

    def _add_warning(
        self,
        document: str,
        error_type: str,
        message: str,
        principle_id: str | None = None,
    ):
        """Add a validation warning."""
        self.warnings.append(
            ValidationError(
                document=document,
                principle_id=principle_id,
                error_type=error_type,
                message=message,
                severity="warning",
            )
        )


# ID: ecf86eed-2f06-4688-9dd2-3fac2586096d
def format_validation_report(report: ValidationReport) -> str:
    """
    Format validation report for console output.

    Args:
        report: ValidationReport to format

    Returns:
        Formatted string ready for printing
    """
    lines = []
    lines.append("=" * 80)
    lines.append("CONSTITUTIONAL META-VALIDATION REPORT")
    lines.append("=" * 80)
    lines.append("")

    status = "✅ VALID" if report.valid else "❌ INVALID"
    lines.append(f"Status: {status}")
    lines.append(f"Documents Checked: {report.documents_checked}")
    lines.append(f"Principles Validated: {report.principles_validated}")
    lines.append(f"Errors: {len(report.errors)}")
    lines.append(f"Warnings: {len(report.warnings)}")
    lines.append("")

    if report.errors:
        lines.append("❌ ERRORS")
        lines.append("-" * 80)
        for error in report.errors:
            location = error.document
            if error.principle_id:
                location += f" → {error.principle_id}"
            lines.append(f"\n{location}")
            lines.append(f"  Type: {error.error_type}")
            lines.append(f"  Message: {error.message}")
        lines.append("")

    lines.append("=" * 80)
    return "\n".join(lines)


if __name__ == "__main__":
    validator = MetaValidator()
    report = validator.validate_constitution()
    logger.info(format_validation_report(report))

    exit(0 if report.valid else 1)
