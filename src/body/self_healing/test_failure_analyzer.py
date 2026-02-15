# src/features/self_healing/test_failure_analyzer.py

"""Analyzes pytest test failures to provide actionable context for fixing tests.

This service parses pytest output to understand what went wrong, extracting:
- Which tests failed
- Expected vs actual values
- Assertion details
- Error messages

This context is then used to guide test fixing iterations.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)

import logging
import re
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
# ID: ce68287c-ce0d-4930-8b6d-e0b1ad881c7a
class TestFailure:
    """Represents a single test failure with context."""

    __test__ = False

    test_name: str
    test_class: str | None
    failure_type: str
    expected: str | None
    actual: str | None
    assertion: str
    error_message: str
    full_context: str

    # ID: 9f359f13-f4f4-4529-8094-da05742defe9
    def to_fix_context(self) -> str:
        """Convert to human-readable context for LLM."""
        lines = []
        if self.test_class:
            lines.append(f"Test: {self.test_class}::{self.test_name}")
        else:
            lines.append(f"Test: {self.test_name}")
        lines.append(f"Failure: {self.failure_type}")
        if self.expected and self.actual:
            lines.append(f"Expected: {self.expected}")
            lines.append(f"Got: {self.actual}")
        if self.assertion:
            lines.append(f"Assertion: {self.assertion}")
        if self.error_message:
            lines.append(f"Error: {self.error_message}")
        return "\n".join(lines)


@dataclass
# ID: e036107b-4c4e-413e-a8d6-179104bb0515
class TestResults:
    """Summary of test execution results."""

    total: int
    passed: int
    failed: int
    failures: list[TestFailure]
    output: str

    @property
    # ID: 3089cc43-f575-4d39-838e-173e6ea33f98
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total == 0:
            return 0.0
        return self.passed / self.total * 100


# ID: 4f440d3f-fede-47ce-b13f-21d1fb93fb8b
class TestFailureAnalyzer:
    """
    Analyzes pytest output to extract actionable failure information.

    This parser handles pytest's verbose output format and extracts
    structured information about what went wrong.
    """

    __test__ = False

    def __init__(self):
        """Initialize the analyzer."""
        pass  # ← Add this

    # ID: b671d25d-006b-4403-a493-eb19575540d3
    def analyze(self, pytest_output: str, pytest_errors: str = "") -> TestResults:
        """
        Parse pytest output and extract failure information.

        Args:
            pytest_output: stdout from pytest
            pytest_errors: stderr from pytest

        Returns:
            TestResults with structured failure information
        """
        combined_output = pytest_output + "\n" + pytest_errors
        summary = self._extract_summary(combined_output)
        failures = self._extract_failures(combined_output)
        return TestResults(
            total=summary["total"],
            passed=summary["passed"],
            failed=summary["failed"],
            failures=failures,
            output=combined_output,
        )

    def _extract_summary(self, output: str) -> dict[str, int]:
        """Extract test count summary from pytest output."""
        summary_pattern = r"(\d+)\s+failed.*?(\d+)\s+passed"
        match = re.search(summary_pattern, output)
        if match:
            failed = int(match.group(1))
            passed = int(match.group(2))
            return {"total": failed + passed, "passed": passed, "failed": failed}
        passed_pattern = r"(\d+)\s+passed"
        match = re.search(passed_pattern, output)
        if match:
            passed = int(match.group(1))
            return {"total": passed, "passed": passed, "failed": 0}
        return {"total": 0, "passed": 0, "failed": 0}

    def _extract_failures(self, output: str) -> list[TestFailure]:
        """Extract detailed failure information from pytest output."""
        failures = []
        failure_lines = self._find_failure_lines(output)
        for line in failure_lines:
            failure = self._parse_failure_line(line, output)
            if failure:
                failures.append(failure)
        return failures

    def _find_failure_lines(self, output: str) -> list[str]:
        """Find all FAILED lines in pytest output."""
        lines = []
        for line in output.split("\n"):
            if line.startswith("FAILED "):
                lines.append(line)
        return lines

    def _parse_failure_line(
        self, failure_line: str, full_output: str
    ) -> TestFailure | None:
        """
        Parse a single FAILED line and extract context.

        Example line:
        FAILED tests/shared/test_header_tools.py::TestHeaderTools::test_parse_empty - AssertionError: assert [] == ['']
        """
        try:
            parts = failure_line.split(" - ", 1)
            if len(parts) < 2:
                return None
            test_path = parts[0].replace("FAILED ", "")
            error_part = parts[1]
            path_parts = test_path.split("::")
            if len(path_parts) == 3:
                test_class = path_parts[1]
                test_name = path_parts[2]
            elif len(path_parts) == 2:
                test_class = None
                test_name = path_parts[1]
            else:
                return None
            failure_type = error_part.split(":")[0].strip()
            expected, actual = self._extract_assertion_values(error_part)
            assertion = self._extract_assertion(error_part)
            context = self._find_failure_context(test_name, full_output)
            return TestFailure(
                test_name=test_name,
                test_class=test_class,
                failure_type=failure_type,
                expected=expected,
                actual=actual,
                assertion=assertion,
                error_message=error_part,
                full_context=context,
            )
        except Exception as e:
            logger.warning("Failed to parse failure line: {failure_line}: %s", e)
            return None

    def _extract_assertion_values(
        self, error_text: str
    ) -> tuple[str | None, str | None]:
        """Extract expected and actual values from assertion error."""
        assert_pattern = r"assert (.+?) == (.+?)(?:\n|$|\s+\+)"
        match = re.search(assert_pattern, error_text)
        if match:
            actual = match.group(1).strip()
            expected = match.group(2).strip()
            return (expected, actual)
        expected_pattern = r"[Ee]xpected:?\s*(.+?)(?:\n|$)"
        actual_pattern = r"[Gg]ot:?\s*(.+?)(?:\n|$)"
        expected_match = re.search(expected_pattern, error_text)
        actual_match = re.search(actual_pattern, error_text)
        expected = expected_match.group(1).strip() if expected_match else None
        actual = actual_match.group(1).strip() if actual_match else None
        return (expected, actual)

    def _extract_assertion(self, error_text: str) -> str:
        """Extract the actual assertion statement."""
        assert_pattern = r"(assert .+?)(?:\n|\s+\+|$)"
        match = re.search(assert_pattern, error_text)
        if match:
            return match.group(1).strip()
        return error_text.split("\n")[0] if error_text else ""

    def _find_failure_context(self, test_name: str, full_output: str) -> str:
        """Find additional context about the failure in full output."""
        lines = full_output.split("\n")
        context_lines = []
        capturing = False
        for line in lines:
            if test_name in line:
                capturing = True
            if capturing:
                context_lines.append(line)
                if line.startswith("FAILED ") and test_name not in line:
                    break
                if line.startswith("===") and len(context_lines) > 5:
                    break
        return "\n".join(context_lines[:30])

    # ID: 88fe19e7-0abc-4abd-a435-1636caa2a229
    def generate_fix_summary(self, results: TestResults) -> str:
        """
        Generate a human-readable summary for the LLM to understand failures.

        This is what gets added to the fix prompt.
        """
        if results.failed == 0:
            return "✅ All tests passed!"
        lines = [
            f"Test Results: {results.passed}/{results.total} passed ({results.success_rate:.1f}%)",
            f"Failures: {results.failed}",
            "",
            "Detailed Failures:",
            "",
        ]
        for i, failure in enumerate(results.failures, 1):
            lines.append(f"FAILURE {i}:")
            lines.append(failure.to_fix_context())
            lines.append("")
        return "\n".join(lines)
