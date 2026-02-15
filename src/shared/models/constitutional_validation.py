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


# ID: d924c000-09ed-4f2e-af1d-aa9bb482455f
# ID: 58d0cdab-1fb1-448c-a078-456553f29cc9
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

    # ID: f4939293-c27c-4326-b919-1bd68446497a
    # ID: 6cff73e5-c95e-41fd-8bee-568684391987
    def add_violation(self, violation: ViolationReport) -> None:
        """
        Add a violation to this result.

        Args:
            violation: ViolationReport to add
        """
        self.violations.append(violation)
        self.is_valid = False

    # ID: d9c88e2e-7726-40f2-a0ae-1577b96f2fb7
    # ID: 12cc1d20-32d5-4823-9a2d-eef6d892bb2d
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

    # ID: f7c42532-e3f8-4dc3-83d3-c63a878e98bc
    # ID: cf0efeb9-f15c-4f40-8fcb-68c6bf003255
    def error_count(self) -> int:
        """
        Count violations with severity 'error'.

        Returns:
            Number of error-level violations
        """
        return sum(1 for v in self.violations if v.severity == "error")

    # ID: 3bde3c7d-c18e-4a60-9b2e-2c7a19582907
    # ID: f8947851-9a7e-4655-8aef-3ac1ea1c711e
    def warning_count(self) -> int:
        """
        Count violations with severity 'warning'.

        Returns:
            Number of warning-level violations
        """
        return sum(1 for v in self.violations if v.severity == "warning")

    # ID: 19676d0c-c56b-4412-be94-ec258e8895b3
    # ID: 240d1988-694a-4ba3-a8c4-105407f3ebb4
    def has_errors(self) -> bool:
        """
        Check if result contains error-level violations.

        Returns:
            True if any violations are errors (not just warnings)
        """
        return any(v.severity == "error" for v in self.violations)


# ID: 7fa2c13c-269c-4892-92d0-7addc0570454
# ID: 7712571e-67fa-4065-a79d-9f053f5a1d36
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
    # ID: 09a94979-da28-41a9-a30a-9b86fdcc186a
    # ID: 1118b562-e215-4bb8-82ef-d8746c3b230a
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


# ID: 1ff12df8-2982-40a6-886a-9a97b3a93f28
# ID: 209ee2a0-37b3-43ec-bfee-59163347ec81
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

    # ID: 498e3155-c693-422c-b51b-0b668608e407
    # ID: 26184315-b398-49d8-acb7-378bb7db16d1
    def add_result(self, result: ConstitutionalValidationResult) -> None:
        """
        Add a validation result to the batch.

        Args:
            result: ConstitutionalValidationResult to add
        """
        self.results.append(result)

    # ID: 20a42412-9225-4c82-a6c5-78ffa7e953f5
    # ID: 5949fa51-73a8-4627-8a64-6e487aae135f
    def has_errors(self) -> bool:
        """
        Check if any results contain error-level violations.

        Returns:
            True if any result has errors
        """
        return any(r.has_errors() for r in self.results)
