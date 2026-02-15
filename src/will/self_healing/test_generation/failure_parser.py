# src/features/self_healing/test_generation/failure_parser.py

"""Specialist for parsing pytest output into structured failure data."""

from __future__ import annotations

import re
from typing import Any


# ID: 2cad9fef-4937-428c-8094-f37103e4f702
class TestFailureParser:
    """Parses pytest output to extract individual test failures."""

    @staticmethod
    # ID: c12c580d-786f-42a0-b29d-525ffdf81db0
    def parse_failures(pytest_output: str) -> list[dict[str, Any]]:
        failures = []
        # Pattern to find FAILED lines
        failed_pattern = r"FAILED ([\w/\.]+::[\w:]+) - (.+)"
        for match in re.finditer(failed_pattern, pytest_output):
            test_path = match.group(1)
            error_type = match.group(2)
            parts = test_path.split("::")
            test_name = parts[-1] if parts else "unknown"

            # Extract basic traceback info (simplified for the fix prompt)
            failures.append(
                {
                    "test_name": test_name,
                    "test_path": test_path,
                    "failure_type": error_type,
                    "error_message": error_type,
                    "full_traceback": f"Test {test_name} failed with {error_type}",
                }
            )
        return failures
