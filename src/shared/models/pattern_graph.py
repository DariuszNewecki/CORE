# src/shared/models/pattern_graph.py
"""
Shared models for pattern validation and compliance.
Resolves duplication between CLI logic and governance checking.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
# ID: 494118ab-afe1-4ef0-ae64-13c6abd9de9a
class PatternViolation:
    """Represents a pattern compliance violation."""

    pattern_id: str | None = (
        None  # Support both validator (id) and checker (expected_pattern)
    )
    violation_type: str = "unknown"
    message: str = ""
    severity: str = "error"  # error, warning, info

    # Fields for context
    file_path: str | None = None
    component_name: str | None = None
    line_number: int | None = None

    # Compatibility aliases for different consumers
    @property
    # ID: 35e4303c-3c6f-4b74-a658-d13671e65571
    def expected_pattern(self) -> str:
        return self.pattern_id or "unknown"


@dataclass
# ID: 85bcca66-0390-4eaf-96e4-079b626c5b5e
class PatternValidationResult:
    """Result of pattern validation."""

    pattern_id: str
    passed: bool
    violations: list[PatternViolation]

    # Fields from checker
    total_components: int = 0
    compliant: int = 0

    @property
    # ID: 7f757ddd-3707-4e3b-9e05-73212d55356f
    def is_approved(self) -> bool:
        """Check if validation passed (no errors)."""
        errors = [v for v in self.violations if v.severity == "error"]
        return len(errors) == 0

    @property
    # ID: 0fc832a9-5857-4a64-8cf1-af7a26456f64
    def compliance_rate(self) -> float:
        """Calculate compliance percentage."""
        if self.total_components == 0:
            return 100.0 if self.passed else 0.0
        return (self.compliant / self.total_components) * 100
