# src/shared/models/constitutional_validation.py

"""
Constitutional Validation Results - Standardized Models for Constitutional Enforcement

CONSTITUTIONAL ALIGNMENT:
- DRY-by-Design: Single source of truth for constitutional validation results
- Used across: IntentSchemaValidator, PathValidator, CodeValidator
- Distinct from generic ValidationResult (validation_result.py)

This module provides constitutional-specific validation types to eliminate duplication
across constitutional enforcement services.

Naming Convention:
- ConstitutionalValidationResult - Rich violation tracking for constitutional rules
- ValidationResult (validation_result.py) - Generic validation with string errors

Both models serve different purposes and coexist without conflict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mind.governance.violation_report import ViolationReport


# ID: constitutional_validation_result
# ID: 1a2b3c4d-5e6f-7890-abcd-ef1234567890
@dataclass
# ID: aef9205f-4ce7-4d8f-a8d2-03fc8dfed1d7
class ConstitutionalValidationResult:
    """
    Constitutional validation result with rich violation tracking.

    Used by constitutional enforcement services:
    - IntentSchemaValidator (schema validation)
    - PathValidator (constitutional rule validation)
    - CodeValidator (code pattern validation)

    Attributes:
        is_valid: Whether validation passed
        violations: List of ViolationReport objects (empty if valid)
        source: Which validator produced this result
        metadata: Additional context (paths, counts, etc.)
    """

    is_valid: bool
    violations: list[ViolationReport] = field(default_factory=list)
    source: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        """Return number of violations (for list-like compatibility)."""
        return len(self.violations)

    # ID: result_add_violation
    # ID: 2b3c4d5e-6f7a-8901-bcde-f12345678901
    def add_violation(self, violation: ViolationReport) -> None:
        """
        Add a violation to this result.

        Args:
            violation: ViolationReport to add
        """
        self.violations.append(violation)
        self.is_valid = False

    # ID: result_merge
    # ID: 3c4d5e6f-7a8b-9012-cdef-123456789012
    def merge(self, other: ConstitutionalValidationResult) -> None:
        """
        Merge another validation result into this one.

        Args:
            other: Another ConstitutionalValidationResult to merge
        """
        self.violations.extend(other.violations)
        if not other.is_valid:
            self.is_valid = False
        self.metadata.update(other.metadata)

    # ID: result_error_count
    # ID: 4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a
    def error_count(self) -> int:
        """
        Count violations with severity 'error'.

        Returns:
            Number of error-level violations
        """
        return sum(1 for v in self.violations if v.severity == "error")

    # ID: result_warning_count
    # ID: 5e6f7a8b-9c0d-1e2f-3a4b-5c6d7e8f9a0b
    def warning_count(self) -> int:
        """
        Count violations with severity 'warning'.

        Returns:
            Number of warning-level violations
        """
        return sum(1 for v in self.violations if v.severity == "warning")

    # ID: result_has_errors
    # ID: 6f7a8b9c-0d1e-2f3a-4b5c-6d7e8f9a0b1c
    def has_errors(self) -> bool:
        """
        Check if result contains error-level violations.

        Returns:
            True if any violations are errors (not just warnings)
        """
        return any(v.severity == "error" for v in self.violations)


# ID: constitutional_file_validation_result
# ID: 7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d
@dataclass
# ID: aa01fd5a-065c-4fcf-86aa-646dc1a04ba4
class ConstitutionalFileValidationResult(ConstitutionalValidationResult):
    """
    Constitutional validation result for a specific file.

    Extends ConstitutionalValidationResult with file-specific metadata.

    Attributes:
        file_path: Path to validated file (repo-relative)
        schema_path: Path to schema used (if applicable)
    """

    file_path: str = ""
    schema_path: str = ""

    @classmethod
    # ID: file_result_from_schema
    # ID: 8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e
    def from_schema_validation(
        cls,
        file_path: str,
        schema_path: str,
        is_valid: bool,
        error_message: str | None = None,
    ) -> ConstitutionalFileValidationResult:
        """
        Create result from schema validation.

        Args:
            file_path: Path to validated file
            schema_path: Path to schema
            is_valid: Whether validation passed
            error_message: Error message if validation failed

        Returns:
            ConstitutionalFileValidationResult instance
        """
        violations = []
        if not is_valid and error_message:
            violations.append(
                ViolationReport(
                    rule_name="schema_validation",
                    path=file_path,
                    message=error_message,
                    severity="error",
                    source_policy=schema_path,
                )
            )

        return cls(
            is_valid=is_valid,
            violations=violations,
            source="schema_validator",
            file_path=file_path,
            schema_path=schema_path,
        )


# ID: constitutional_batch_validation_result
# ID: 9c0d1e2f-3a4b-5c6d-7e8f-9a0b1c2d3e4f
@dataclass
# ID: df2617e5-2765-41f5-b73e-023428156c39
class ConstitutionalBatchValidationResult:
    """
    Result from validating multiple files/paths constitutionally.

    Aggregates individual ConstitutionalValidationResults for reporting.

    Attributes:
        results: Individual validation results
    """

    results: list[ConstitutionalValidationResult] = field(default_factory=list)

    @property
    # ID: a55072a5-8344-4722-ae57-2003aa2acf2c
    def is_valid(self) -> bool:
        """All results must be valid for batch to be valid."""
        return all(r.is_valid for r in self.results)

    @property
    # ID: 83772877-9105-49a5-bcf5-3197499b3c4b
    def total_files(self) -> int:
        """Total number of files validated."""
        return len(self.results)

    @property
    # ID: 7641b90c-c082-4f8a-8c6b-01fc1930c8ac
    def valid_count(self) -> int:
        """Number of valid files."""
        return sum(1 for r in self.results if r.is_valid)

    @property
    # ID: ebc08dc8-000d-4446-a7a5-7f1ff49066ae
    def invalid_count(self) -> int:
        """Number of invalid files."""
        return sum(1 for r in self.results if not r.is_valid)

    @property
    # ID: edfa9919-35d3-4573-8295-4d992a8caced
    def all_violations(self) -> list[ViolationReport]:
        """All violations across all results."""
        violations = []
        for result in self.results:
            violations.extend(result.violations)
        return violations

    @property
    # ID: a013eda5-15fd-496c-a535-7bb1b57917ae
    def total_errors(self) -> int:
        """Total error-level violations across all results."""
        return sum(r.error_count() for r in self.results)

    @property
    # ID: 34a1cd62-fc17-4831-83c5-dd0e60fc32c0
    def total_warnings(self) -> int:
        """Total warning-level violations across all results."""
        return sum(r.warning_count() for r in self.results)

    # ID: batch_add_result
    # ID: 0d1e2f3a-4b5c-6d7e-8f9a-0b1c2d3e4f5a
    def add_result(self, result: ConstitutionalValidationResult) -> None:
        """
        Add a validation result to the batch.

        Args:
            result: ConstitutionalValidationResult to add
        """
        self.results.append(result)

    # ID: batch_has_errors
    # ID: 1e2f3a4b-5c6d-7e8f-9a0b-1c2d3e4f5a6b
    def has_errors(self) -> bool:
        """
        Check if any results contain error-level violations.

        Returns:
            True if any result has errors
        """
        return any(r.has_errors() for r in self.results)
