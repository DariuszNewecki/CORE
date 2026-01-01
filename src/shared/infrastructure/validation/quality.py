# src/shared/infrastructure/validation/quality.py

"""
Code quality validation checks for maintainability and clarity.

This module provides quality-focused validation checks such as detecting
FUTURE comments and other code clarity issues that don't affect functionality
but impact maintainability.
"""

from __future__ import annotations

from typing import Any


Violation = dict[str, Any]


# ID: 0c6502f3-6d97-41e8-a618-6ae63a489e8b
class QualityChecker:
    """Handles code quality and clarity validation checks."""

    # ID: 972208ef-200e-4836-851d-f82f24e3b779
    def check_for_todo_comments(self, code: str) -> list[Violation]:
        """Scans source code for FUTURE/PENDING comments and returns them as violations.

        Args:
            code: The source code to scan for FUTURE comments

        Returns:
            List of violations for each FUTURE/PENDING comment found
        """
        violations: list[Violation] = []
        for i, line in enumerate(code.splitlines(), 1):
            if "#" in line:
                comment = line.split("#", 1)[1]
                if "FUTURE" in comment or "PENDING" in comment:
                    violations.append(
                        {
                            "rule": "clarity.no_todo_comments",
                            "message": f"Unresolved '{comment.strip()}' on line {i}",
                            "line": i,
                            "severity": "warning",
                        }
                    )
        return violations
