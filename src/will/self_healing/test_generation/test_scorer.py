# src/features/self_healing/test_generation/test_scorer.py

"""
Pytest output parsing and test scoring utilities.
"""

from __future__ import annotations

import re


# ID: 4f6fab17-07a6-43e5-817a-4db72da84773
class TestScorer:
    """Parse pytest output and extract test execution metrics."""

    @staticmethod
    # ID: 9d4dd803-79ac-4368-921a-2d9a0a325cb6
    def count_passed(pytest_output: str) -> int:
        """Extract passed test count from pytest output."""
        match = re.search(r"(\d+) passed", pytest_output)
        return int(match.group(1)) if match else 0

    @staticmethod
    # ID: ec1a1e4c-a900-4dca-b5e3-1ff5d7ec44af
    def count_failed(pytest_output: str) -> int:
        """Extract failed test count from pytest output."""
        match = re.search(r"(\d+) failed", pytest_output)
        return int(match.group(1)) if match else 0

    @staticmethod
    # ID: 19d041d2-d409-400f-96df-72a0ec499a14
    def count_total(pytest_output: str) -> int:
        """Extract total test count from pytest output."""
        passed = TestScorer.count_passed(pytest_output)
        failed = TestScorer.count_failed(pytest_output)
        return passed + failed

    @staticmethod
    # ID: 08410d85-7799-42d0-9b1c-34a435bd68b3
    def calculate_pass_rate(pytest_output: str) -> float:
        """Calculate pass rate percentage from pytest output."""
        total = TestScorer.count_total(pytest_output)
        if total == 0:
            return 0.0
        passed = TestScorer.count_passed(pytest_output)
        return (passed / total) * 100

    @staticmethod
    # ID: e8e4a684-4040-4ed8-a27c-7e75268de204
    def format_score(passed: int, total: int) -> str:
        """Format test score as readable string."""
        rate = (passed / total * 100) if total > 0 else 0
        return f"{passed}/{total} ({rate:.0f}%)"
