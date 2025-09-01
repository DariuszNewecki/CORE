# src/core/validation_quality.py
"""
Code quality validation checks for maintainability and clarity.

This module provides quality-focused validation checks such as detecting
TODO comments and other code clarity issues that don't affect functionality
but impact maintainability.
"""

from __future__ import annotations

from typing import Any, Dict, List

Violation = Dict[str, Any]


# CAPABILITY: audit.check.code_quality
class QualityChecker:
    """Handles code quality and clarity validation checks."""

    # CAPABILITY: audit.check.todo_comments
    def check_for_todo_comments(self, code: str) -> List[Violation]:
        """Scans source code for TODO/FIXME comments and returns them as violations.

        Args:
            code: The source code to scan for TODO comments

        Returns:
            List of violations for each TODO/FIXME comment found
        """
        violations: List[Violation] = []
        for i, line in enumerate(code.splitlines(), 1):
            if "#" in line:
                comment = line.split("#", 1)[1]
                if "TODO" in comment or "FIXME" in comment:
                    violations.append(
                        {
                            "rule": "clarity.no_todo_comments",
                            "message": f"Unresolved '{comment.strip()}' on line {i}",
                            "line": i,
                            "severity": "warning",
                        }
                    )
        return violations
