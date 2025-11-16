# src/mind/governance/checks/coverage_check.py
"""
Constitutional enforcement of test coverage requirements.

Verifies that the codebase meets the coverage requirements defined in the
quality_assurance policy.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity

from mind.governance.audit_context import AuditorContext

# Import the BaseCheck to inherit from it
from mind.governance.checks.base_check import BaseCheck

logger = getLogger(__name__)


# ID: f09915fb-02c8-49d4-b5c5-19cd5e955df4
# Inherit from BaseCheck
# ID: 365e9a78-c99e-4b36-82a8-6a1ba5e08fd4
class CoverageGovernanceCheck(BaseCheck):
    """
    Enforces constitutional test coverage requirements.

    This check verifies that:
    1. Overall coverage meets the minimum threshold.
    2. Critical paths meet their specific higher thresholds.
    3. No significant coverage regressions have occurred.
    """

    # Fulfills the contract from BaseCheck. These are the primary rules in the
    # quality_assurance policy that this check is responsible for enforcing.
    policy_rule_ids = [
        "coverage.minimum_threshold",
        "coverage.no_untested_commits",
    ]

    def __init__(self, context: AuditorContext) -> None:
        """Initializes the check using the context provided by BaseCheck."""
        super().__init__(context)
        # Get the policy from the shared context instead of loading it manually.
        policy = self.context.policies.get("quality_assurance", {})
        coverage_cfg = policy.get("coverage_requirements", {})

        self.minimum_threshold: float = coverage_cfg.get("minimum_threshold", 75.0)
        self.critical_paths: list[str] = coverage_cfg.get("critical_paths", [])
        self.exclusions: list[str] = coverage_cfg.get("exclusions", [])

    # ID: a8126c8d-f9b8-40d5-a098-4aa5065f656c
    # The original was async, we keep it that way assuming the auditor can handle it.
    # ID: e11f1d23-6432-4b99-80a7-b246b5123c50
    async def execute(self) -> list[AuditFinding]:
        """
        Executes the coverage check and returns audit findings.
        """
        findings: list[AuditFinding] = []

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

        overall_coverage = coverage_data.get("overall_percent", 0.0)

        # 1) Enforce coverage.minimum_threshold
        if overall_coverage < self.minimum_threshold:
            findings.append(
                AuditFinding(
                    check_id="coverage.minimum_threshold",
                    severity=AuditSeverity.ERROR,
                    message=(
                        f"Coverage {overall_coverage}% below constitutional minimum "
                        f"{self.minimum_threshold}%"
                    ),
                    file_path="N/A",
                    context={
                        "current": overall_coverage,
                        "required": self.minimum_threshold,
                        "delta": overall_coverage - self.minimum_threshold,
                        "action": "Trigger autonomous remediation",
                    },
                )
            )

        # 2) Enforce critical path thresholds
        for path_spec in self._iter_critical_path_specs():
            path_pattern, required = self._parse_path_spec(path_spec)
            actual = self._get_path_coverage(coverage_data, path_pattern)
            if actual is not None and actual < required:
                findings.append(
                    AuditFinding(
                        # Structured check_id to show it's a specific violation
                        # of the minimum threshold rule.
                        check_id="coverage.minimum_threshold.critical_path",
                        severity=AuditSeverity.ERROR,
                        message=(
                            f"Critical path '{path_pattern}' coverage {actual}% "
                            f"below required {required}%"
                        ),
                        file_path=path_pattern,
                        context={
                            "current": actual,
                            "required": required,
                            "delta": actual - required,
                        },
                    )
                )

        # 3) Enforce coverage.no_untested_commits (regression check)
        regression = self._check_regression(coverage_data)
        if regression:
            findings.append(regression)

        return findings

    def _measure_coverage(self) -> dict[str, Any] | None:
        """Runs pytest with coverage and returns parsed results."""
        try:
            # Use self.repo_root from BaseCheck for consistency
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
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=300,
            )

            coverage_json = self.repo_root / "coverage.json"
            if coverage_json.exists():
                data = json.loads(coverage_json.read_text())
                totals = data.get("totals", {})
                return {
                    "overall_percent": float(totals.get("percent_covered", 0) or 0),
                    "lines_covered": int(totals.get("covered_lines", 0) or 0),
                    "lines_total": int(totals.get("num_statements", 0) or 0),
                    "files": data.get("files", {}),
                    "timestamp": data.get("meta", {}).get("timestamp"),
                }
            return self._parse_term_output(result.stdout)
        except subprocess.TimeoutExpired:
            logger.error("Coverage measurement timed out after 5 minutes")
            return None
        except Exception as exc:
            logger.error("Failed to measure coverage: %s", exc, exc_info=True)
            return None

    def _parse_term_output(self, output: str) -> dict[str, Any] | None:
        """Fallback parser for terminal coverage output."""
        try:
            for line in output.splitlines():
                if line.startswith("TOTAL"):
                    parts = line.split()
                    if len(parts) >= 4:
                        percent_str = parts[-1].rstrip("%")
                        percent = float(percent_str)
                        total_lines = int(parts[1])
                        missed_lines = int(parts[2])
                        covered_lines = total_lines - missed_lines
                        return {
                            "overall_percent": percent,
                            "lines_total": total_lines,
                            "lines_covered": covered_lines,
                        }
        except Exception as exc:
            logger.debug("Failed to parse coverage output: %s", exc)
        return None

    def _iter_critical_path_specs(self) -> list[str]:
        """Returns the list of critical path specifications."""
        return list(self.critical_paths or [])

    def _parse_path_spec(self, spec: str) -> tuple[str, float]:
        """Parses a path specification like 'src/core/**/*.py: 85%'."""
        parts = spec.split(":", maxsplit=1)
        path = parts[0].strip()
        percent_str = parts[1].strip().rstrip("%") if len(parts) > 1 else "0"
        required = float(percent_str or 0)
        return path, required

    def _get_path_coverage(
        self, coverage_data: dict[str, Any], pattern: str
    ) -> float | None:
        """Gets coverage percentage for files matching a pattern."""
        from fnmatch import fnmatch

        files = coverage_data.get("files", {})
        if not files:
            return None
        total_lines, covered_lines = 0, 0
        for file_path, file_data in files.items():
            if fnmatch(file_path, pattern):
                summary = file_data.get("summary", {})
                total_lines += int(summary.get("num_statements", 0) or 0)
                covered_lines += int(summary.get("covered_lines", 0) or 0)
        if total_lines == 0:
            return None
        return round(covered_lines / total_lines * 100, 2)

    def _check_regression(self, coverage_data: dict[str, Any]) -> AuditFinding | None:
        """Checks for significant coverage regressions."""
        # Use self.repo_root from BaseCheck for consistency
        history_file = self.repo_root / "work" / "testing" / "coverage_history.json"
        if not history_file.exists():
            self._save_coverage_history(coverage_data)
            return None
        try:
            history = json.loads(history_file.read_text())
            last_run = history.get("last_run", {})
            last_percent = float(last_run.get("overall_percent", 0) or 0)
            current_percent = float(coverage_data.get("overall_percent", 0) or 0)
            delta = current_percent - last_percent
            self._save_coverage_history(coverage_data)
            if delta < -5.0:
                # This finding correctly uses the constitutional rule ID.
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
        except Exception as exc:
            logger.debug("Could not check coverage regression: %s", exc)
        return None

    def _save_coverage_history(self, coverage_data: dict[str, Any]) -> None:
        """Saves coverage data to history file for regression tracking."""
        try:
            # Use self.repo_root from BaseCheck for consistency
            history_file = self.repo_root / "work" / "testing" / "coverage_history.json"
            history_file.parent.mkdir(parents=True, exist_ok=True)
            history = {
                "last_run": coverage_data,
                "updated_at": coverage_data.get("timestamp"),
            }
            history_file.write_text(json.dumps(history, indent=2))
        except Exception as exc:
            logger.debug("Could not save coverage history: %s", exc)
