# src/shared/models/constitutional_validation.py

"""
Constitutional Validation Results - Standardized Models for Constitutional Enforcement

CONSTITUTIONAL ALIGNMENT:
- DRY-by-Design: Single source of truth for constitutional validation results
- P2.3 Fix: Purged upward dependency to Mind layer (ViolationReport). Uses duck-typing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


# ID: 0e2d9e1a-b99e-468d-95a5-75778dc7f301
class ViolationLike(Protocol):
    """Duck-typing protocol for violation reports to avoid Mind-layer imports."""

    severity: str
    rule_name: str
    message: str
    path: str


def _get_severity(v: Any) -> str:
    """Safely extract severity from either a dict or a ViolationReport object."""
    if isinstance(v, dict):
        return v.get("severity", "error")
    return getattr(v, "severity", "error")


@dataclass
# ID: c8e3bcd9-66f6-4bec-bb7e-977122014c1f
class ConstitutionalValidationResult:
    """
    Constitutional validation result with rich violation tracking.
    """

    is_valid: bool
    violations: list[Any] = field(default_factory=list)
    source: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        """Return number of violations (for list-like compatibility)."""
        return len(self.violations)

    # ID: 1dd947b6-67c3-4b22-b969-044aa20ffce6
    def add_violation(self, violation: Any) -> None:
        """Add a violation to this result."""
        self.violations.append(violation)
        self.is_valid = False

    # ID: 5b7c9136-59df-4528-860a-b02274d7bc2b
    def merge(self, other: ConstitutionalValidationResult) -> None:
        """Merge another validation result into this one."""
        self.violations.extend(other.violations)
        if not other.is_valid:
            self.is_valid = False
        self.metadata.update(other.metadata)

    # ID: 35c67f0d-d000-4f45-98f5-f34a45816a8c
    def error_count(self) -> int:
        """Count violations with severity 'error'."""
        return sum(1 for v in self.violations if _get_severity(v) == "error")

    # ID: 25ed2c65-6407-42ab-8424-b9f0e243661f
    def warning_count(self) -> int:
        """Count violations with severity 'warning'."""
        return sum(1 for v in self.violations if _get_severity(v) == "warning")

    # ID: 2a74ba9a-e24a-495b-9781-ddbc20e5a876
    def has_errors(self) -> bool:
        """Check if result contains error-level violations."""
        return any(_get_severity(v) == "error" for v in self.violations)


@dataclass
# ID: a88c9658-f4e0-42ea-92a6-565cabfb9200
class ConstitutionalFileValidationResult(ConstitutionalValidationResult):
    """
    Constitutional validation result for a specific file.
    """

    file_path: str = ""
    schema_path: str = ""

    @classmethod
    # ID: aea7bca0-d2ac-4105-a011-8abc59815674
    def from_schema_validation(
        cls,
        file_path: str,
        schema_path: str,
        is_valid: bool,
        error_message: str | None = None,
    ) -> ConstitutionalFileValidationResult:
        """Create result from schema validation."""
        violations = []
        if not is_valid and error_message:
            # We use a simple dict here to avoid importing ViolationReport,
            # ensuring the shared layer remains pure.
            violations.append(
                {
                    "rule_name": "schema_validation",
                    "path": file_path,
                    "message": error_message,
                    "severity": "error",
                    "source_policy": schema_path,
                }
            )

        return cls(
            is_valid=is_valid,
            violations=violations,
            source="schema_validator",
            file_path=file_path,
            schema_path=schema_path,
        )


@dataclass
# ID: e5b34796-abf5-4aa1-afc6-6d3323bc5966
class ConstitutionalBatchValidationResult:
    """
    Result from validating multiple files/paths constitutionally.
    """

    results: list[ConstitutionalValidationResult] = field(default_factory=list)

    @property
    # ID: 10e200df-d9f9-4ed4-8580-5d552d01280f
    def is_valid(self) -> bool:
        """All results must be valid for batch to be valid."""
        return all(r.is_valid for r in self.results)

    @property
    # ID: 6a9b2f69-7ae7-47c9-8fa6-1ec5e50150a3
    def total_files(self) -> int:
        """Total number of files validated."""
        return len(self.results)

    @property
    # ID: b6af6fc8-096b-4528-a223-0f71ebaf3e1f
    def valid_count(self) -> int:
        """Number of valid files."""
        return sum(1 for r in self.results if r.is_valid)

    @property
    # ID: 220ee2a3-8371-4f7f-828e-ff9e405638d9
    def invalid_count(self) -> int:
        """Number of invalid files."""
        return sum(1 for r in self.results if not r.is_valid)

    @property
    # ID: 6db1bbed-2956-4d73-9457-07f18f342a9b
    def all_violations(self) -> list[Any]:
        """All violations across all results."""
        violations = []
        for result in self.results:
            violations.extend(result.violations)
        return violations

    @property
    # ID: e9324cd4-fece-450d-89fd-59878991e4fd
    def total_errors(self) -> int:
        """Total error-level violations across all results."""
        return sum(r.error_count() for r in self.results)

    @property
    # ID: f45364fe-f812-450b-ab4e-d792b0c0a58e
    def total_warnings(self) -> int:
        """Total warning-level violations across all results."""
        return sum(r.warning_count() for r in self.results)

    # ID: b009e19e-8c5e-4ae0-8d4f-17a5f0dcb85f
    def add_result(self, result: ConstitutionalValidationResult) -> None:
        """Add a validation result to the batch."""
        self.results.append(result)

    # ID: 3f100fc5-c403-4f88-ae37-3b8b07d609ae
    def has_errors(self) -> bool:
        """Check if any results contain error-level violations."""
        return any(r.has_errors() for r in self.results)
