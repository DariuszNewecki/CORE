# src/features/self_healing/complexity_filter.py

"""
Provides a simple, stateless filter to determine if a file's complexity
is within an acceptable threshold for autonomous test generation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from radon.visitors import ComplexityVisitor

from shared.logger import getLogger

logger = getLogger(__name__)
COMPLEXITY_THRESHOLDS = {"SIMPLE": 5, "MODERATE": 15, "COMPLEX": 50}


# ID: c020e1c4-89a7-4933-a859-920ffea4244e
class ComplexityFilter:
    """
    Determines if a file should be attempted for remediation based on complexity.
    """

    def __init__(self, max_complexity: str = "MODERATE"):
        """
        Args:
            max_complexity: The maximum complexity level to allow (SIMPLE, MODERATE, COMPLEX).
        """
        self.threshold = COMPLEXITY_THRESHOLDS.get(max_complexity.upper(), 15)

    # ID: cc7541ee-4499-4483-a8b8-c6256e69573a
    def should_attempt(self, file_path: Path) -> dict[str, Any]:
        """
        Analyzes a file and decides if it's simple enough to attempt.

        Returns:
            A dictionary with 'should_attempt', 'reason', and 'complexity'.
        """
        try:
            source_code = file_path.read_text("utf-8")
            visitor = ComplexityVisitor.from_code(source_code)
            if visitor.complexity > self.threshold * 2:
                return {
                    "should_attempt": False,
                    "reason": "Module complexity too high",
                    "complexity": visitor.complexity,
                }
            for func in visitor.functions:
                if func.complexity > self.threshold:
                    return {
                        "should_attempt": False,
                        "reason": f"Function '{func.name}' is too complex ({func.complexity})",
                        "complexity": func.complexity,
                    }
            return {
                "should_attempt": True,
                "reason": "Complexity is within threshold",
                "complexity": visitor.complexity,
            }
        except Exception as e:
            logger.warning(f"Could not analyze complexity for {file_path}: {e}")
            return {
                "should_attempt": False,
                "reason": "Failed to analyze complexity",
                "complexity": -1,
            }
