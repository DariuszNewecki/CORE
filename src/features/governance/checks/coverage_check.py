# src/features/governance/checks/coverage_check.py
"""
Constitutional enforcement of test coverage requirements.
Verifies that the codebase meets the minimum coverage threshold defined
in the quality_assurance_policy.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

from shared.config import settings
from shared.logger import getLogger
from shared.models.audit_models import AuditFinding, AuditSeverity

log = getLogger(__name__)


# ID: 58e3cb65-b3b5-42f2-bd5f-b9c4ad6e1f1b
class CoverageGovernanceCheck:
    """
    Enforces constitutional test coverage requirements.

    This check verifies that:
    1. Overall coverage meets the minimum threshold (75%)
    2. Critical paths meet their specific higher thresholds
    3. No significant coverage regressions have occurred
    """

    def __init__(self):
        self.policy = settings.load(
            "charter.policies.governance.quality_assurance_policy"
        )
        self.config = self.policy.get("coverage_config", {})
        self.minimum_threshold = self.config.get("minimum_threshold", 75)
        self.critical_paths = self.config.get("critical_paths", [])
        self.exclusions = self.config.get("exclusions", [])

    # ID: e79a372d-8db3-4a04-bce0-c88fc5c051fe
    async def execute(self) -> list[AuditFinding]:
        """
        Executes the coverage check and returns audit findings.

        Returns:
            List of AuditFinding objects for any violations
        """
        findings: list[AuditFinding] = []

        # Get current coverage metrics
        coverage_data = self._measure_coverage()

        if not coverage_data:
            return [
                AuditFinding(
                    check_id="coverage.minimum_threshold",
                    severity=AuditSeverity.ERROR,
                    message="Failed to measure test coverage",
                    file_path="N/A",
                    context={"error": "Could not run pytest coverage"},
                )
            ]

        # Check overall coverage
        overall_coverage = coverage_data.get("overall_percent", 0)
        if overall_coverage < self.minimum_threshold:
            findings.append(
                AuditFinding(
                    check_id="coverage.minimum_threshold",
                    severity=AuditSeverity.ERROR,
                    message=f"Coverage {overall_coverage}% below constitutional minimum {self.minimum_threshold}%",
                    file_path="N/A",
                    context={
                        "current": overall_coverage,
                        "required": self.minimum_threshold,
                        "delta": overall_coverage - self.minimum_threshold,
                        "action": "Trigger autonomous remediation",
                    },
                )
            )

        # Check critical paths
        for path_spec in self.critical_paths:
            path_pattern, required = self._parse_path_spec(path_spec)
            actual = self._get_path_coverage(coverage_data, path_pattern)

            if actual is not None and actual < required:
                findings.append(
                    AuditFinding(
                        check_id="coverage.critical_path",
                        severity=AuditSeverity.ERROR,
                        message=f"Critical path '{path_pattern}' coverage {actual}% below required {required}%",
                        file_path=path_pattern,
                        context={
                            "current": actual,
                            "required": required,
                            "delta": actual - required,
                        },
                    )
                )

        # Check for significant regressions
        regression = self._check_regression(coverage_data)
        if regression:
            findings.append(regression)

        return findings

    def _measure_coverage(self) -> dict[str, Any] | None:
        """
        Runs pytest with coverage and returns parsed results.

        Returns:
            Dict with coverage metrics or None if measurement fails
        """
        try:
            # Run pytest with JSON report for machine parsing
            result = subprocess.run(
                [
                    "poetry",
                    "run",
                    "pytest",
                    "--cov=src",
                    "--cov-report=json",
                    "--cov-report=term",
                    "-q",
                ],
                cwd=settings.REPO_PATH,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            # Read the JSON report
            coverage_json = settings.REPO_PATH / "coverage.json"
            if coverage_json.exists():
                data = json.loads(coverage_json.read_text())

                # Extract key metrics
                totals = data.get("totals", {})
                return {
                    "overall_percent": totals.get("percent_covered", 0),
                    "lines_covered": totals.get("covered_lines", 0),
                    "lines_total": totals.get("num_statements", 0),
                    "files": data.get("files", {}),
                    "timestamp": data.get("meta", {}).get("timestamp"),
                }

            # Fallback: parse terminal output
            return self._parse_term_output(result.stdout)

        except subprocess.TimeoutExpired:
            log.error("Coverage measurement timed out after 5 minutes")
            return None
        except Exception as e:
            log.error(f"Failed to measure coverage: {e}", exc_info=True)
            return None

    def _parse_term_output(self, output: str) -> dict[str, Any] | None:
        """
        Fallback parser for terminal coverage output.

        Args:
            output: Terminal output from pytest --cov

        Returns:
            Dict with coverage metrics or None
        """
        try:
            # Look for TOTAL line: "TOTAL    1234    567    54%"
            for line in output.splitlines():
                if line.startswith("TOTAL"):
                    parts = line.split()
                    if len(parts) >= 4:
                        percent_str = parts[-1].rstrip("%")
                        return {
                            "overall_percent": float(percent_str),
                            "lines_total": int(parts[1]),
                            "lines_covered": int(parts[1]) - int(parts[2]),
                        }
        except Exception as e:
            log.debug(f"Failed to parse coverage output: {e}")

        return None

    def _parse_path_spec(self, spec: str) -> tuple[str, float]:
        """
        Parses a path specification like 'src/core/**/*.py: 85%'.

        Args:
            spec: Path specification string

        Returns:
            Tuple of (path_pattern, required_percent)
        """
        parts = spec.split(":")
        path = parts[0].strip()
        percent = float(parts[1].strip().rstrip("%"))
        return path, percent

    def _get_path_coverage(self, coverage_data: dict, pattern: str) -> float | None:
        """
        Gets coverage percentage for files matching a pattern.

        Args:
            coverage_data: Coverage data from measurement
            pattern: Glob-style path pattern

        Returns:
            Coverage percentage or None if no matches
        """
        files = coverage_data.get("files", {})
        if not files:
            return None

        # Convert pattern to Path for matching
        from fnmatch import fnmatch

        total_lines = 0
        covered_lines = 0

        for file_path, file_data in files.items():
            if fnmatch(file_path, pattern):
                summary = file_data.get("summary", {})
                total_lines += summary.get("num_statements", 0)
                covered_lines += summary.get("covered_lines", 0)

        if total_lines == 0:
            return None

        return round((covered_lines / total_lines) * 100, 2)

    def _check_regression(self, coverage_data: dict) -> AuditFinding | None:
        """
        Checks for significant coverage regressions.

        Args:
            coverage_data: Current coverage data

        Returns:
            AuditFinding if regression detected, None otherwise
        """
        # Read historical coverage from ledger
        history_file = settings.REPO_PATH / "work" / "testing" / "coverage_history.json"

        if not history_file.exists():
            # First run, save baseline
            self._save_coverage_history(coverage_data)
            return None

        try:
            history = json.loads(history_file.read_text())
            last_run = history.get("last_run", {})
            last_percent = last_run.get("overall_percent", 0)
            current_percent = coverage_data.get("overall_percent", 0)

            delta = current_percent - last_percent

            # Save current as latest
            self._save_coverage_history(coverage_data)

            # Check for significant drop
            if delta < -5.0:  # More than 5% drop
                return AuditFinding(
                    check_id="coverage.no_untested_commits",
                    severity=AuditSeverity.ERROR,
                    message=f"Significant coverage regression: {abs(delta):.1f}% drop",
                    file_path="N/A",
                    context={
                        "previous": last_percent,
                        "current": current_percent,
                        "delta": delta,
                    },
                )
        except Exception as e:
            log.debug(f"Could not check coverage regression: {e}")

        return None

    def _save_coverage_history(self, coverage_data: dict) -> None:
        """Saves coverage data to history file for regression tracking."""
        try:
            history_file = (
                settings.REPO_PATH / "work" / "testing" / "coverage_history.json"
            )
            history_file.parent.mkdir(parents=True, exist_ok=True)

            history = {
                "last_run": coverage_data,
                "updated_at": coverage_data.get("timestamp"),
            }

            history_file.write_text(json.dumps(history, indent=2))
        except Exception as e:
            log.debug(f"Could not save coverage history: {e}")
