# src/mind/governance/checks/coverage_governance_check.py
"""
Enforces constitutional test coverage requirements.

Ref: .intent/charter/standards/operations/quality_assurance.json
"""

from __future__ import annotations

import json
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

QA_POLICY = Path(".intent/charter/standards/operations/quality_assurance.json")


# ID: coverage-minimum-threshold-enforcement
# ID: 72879dde-7641-4a7c-b9a7-30f8de690bbb
class CoverageMinimumThresholdEnforcement(EnforcementMethod):
    """
    Enforces minimum test coverage threshold and critical path coverage.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)
        self.minimum_threshold = 75.0  # From qa.coverage.minimum_threshold
        self.critical_paths = []  # Can be extended from rule_data

    # ID: 2f035330-158b-4370-8295-5cdd4bc8eb28
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any]
    ) -> list[AuditFinding]:
        findings = []

        coverage_data = self._measure_coverage(context)

        # If no data, we cannot enforce. Flag as WARNING (Missing Evidence).
        if not coverage_data:
            findings.append(
                AuditFinding(
                    check_id="coverage.data_missing",
                    severity=AuditSeverity.WARNING,
                    message="Coverage data (coverage.json) not found. Cannot verify compliance.",
                    file_path="coverage.json",
                    context={
                        "suggestion": "Run `core-admin check tests` to generate data."
                    },
                )
            )
            return findings

        overall_coverage = coverage_data.get("overall_percent", 0.0)

        # 1) Enforce Minimum Threshold
        if overall_coverage < self.minimum_threshold:
            findings.append(
                self._create_finding(
                    message=(
                        f"Coverage {overall_coverage}% is below constitutional minimum "
                        f"of {self.minimum_threshold}%."
                    ),
                    file_path="coverage.json",
                )
            )

        # 2) Enforce Critical Paths (if configured)
        for path_spec in self.critical_paths:
            path_pattern, required = self._parse_path_spec(path_spec)
            actual = self._get_path_coverage(coverage_data, path_pattern)

            if actual is not None and actual < required:
                findings.append(
                    self._create_finding(
                        message=(
                            f"Critical path '{path_pattern}' coverage {actual}% "
                            f"below required {required}%."
                        ),
                        file_path=path_pattern,
                    )
                )

        return findings

    def _measure_coverage(self, context: AuditorContext) -> dict[str, Any] | None:
        """Loads coverage data from coverage.json (produced by pytest-cov)."""
        coverage_json = context.repo_path / "coverage.json"

        if not coverage_json.exists():
            return None

        try:
            data = json.loads(coverage_json.read_text())
            totals = data.get("totals", {})
            return {
                "overall_percent": float(totals.get("percent_covered", 0) or 0),
                "lines_covered": int(totals.get("covered_lines", 0) or 0),
                "lines_total": int(totals.get("num_statements", 0) or 0),
                "files": data.get("files", {}),
                "timestamp": data.get("meta", {}).get("timestamp"),
            }
        except Exception as exc:
            logger.error("Failed to parse coverage.json: %s", exc)
            return None

    def _parse_path_spec(self, spec: str) -> tuple[str, float]:
        """Parses 'src/core/**/*.py: 85%' into ('src/core/**/*.py', 85.0)."""
        parts = spec.split(":", maxsplit=1)
        path = parts[0].strip()
        percent_str = parts[1].strip().rstrip("%") if len(parts) > 1 else "0"
        return path, float(percent_str or 0)

    def _get_path_coverage(
        self, coverage_data: dict[str, Any], pattern: str
    ) -> float | None:
        """Calculates aggregated coverage for files matching a glob pattern."""
        files = coverage_data.get("files", {})
        if not files:
            return None

        total_lines = 0
        covered_lines = 0

        for file_path, file_data in files.items():
            if fnmatch(file_path, pattern):
                summary = file_data.get("summary", {})
                total_lines += int(summary.get("num_statements", 0) or 0)
                covered_lines += int(summary.get("covered_lines", 0) or 0)

        if total_lines == 0:
            return None

        return round((covered_lines / total_lines) * 100, 2)


# ID: coverage-regression-enforcement
# ID: 82e04f70-1036-4c69-9cf9-7542d321b99e
class CoverageRegressionEnforcement(EnforcementMethod):
    """
    Enforces qa.coverage.no_regression - coverage must not drop significantly.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: c40a6fa6-1f90-43c8-8763-96cdf97724d1
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any]
    ) -> list[AuditFinding]:
        findings = []

        coverage_json = context.repo_path / "coverage.json"
        if not coverage_json.exists():
            return findings

        try:
            data = json.loads(coverage_json.read_text())
            totals = data.get("totals", {})
            coverage_data = {
                "overall_percent": float(totals.get("percent_covered", 0) or 0),
                "timestamp": data.get("meta", {}).get("timestamp"),
            }
        except Exception:
            return findings

        regression = self._check_regression(context, coverage_data)
        if regression:
            findings.append(regression)

        return findings

    def _check_regression(
        self, context: AuditorContext, coverage_data: dict[str, Any]
    ) -> AuditFinding | None:
        """Checks if coverage has dropped significantly (>5%) since last run."""
        history_file = context.repo_path / ".intent/mind/history/coverage_history.json"

        try:
            if history_file.exists():
                history = json.loads(history_file.read_text())
                last_percent = float(
                    history.get("last_run", {}).get("overall_percent", 0)
                )
                current_percent = float(coverage_data.get("overall_percent", 0))
                delta = current_percent - last_percent

                self._save_coverage_history(history_file, coverage_data)

                if delta < -5.0:
                    return self._create_finding(
                        message=f"Significant coverage regression: {abs(delta):.1f}% drop.",
                        file_path="N/A",
                    )
            else:
                self._save_coverage_history(history_file, coverage_data)

        except Exception as exc:
            logger.warning("Coverage regression check failed: %s", exc)

        return None

    def _save_coverage_history(
        self, history_file: Path, coverage_data: dict[str, Any]
    ) -> None:
        """Persists current coverage state for future regression checks."""
        try:
            history_file.parent.mkdir(parents=True, exist_ok=True)
            history = {
                "last_run": coverage_data,
                "updated_at": coverage_data.get("timestamp"),
            }
            history_file.write_text(json.dumps(history, indent=2))
        except Exception as exc:
            logger.warning("Could not save coverage history: %s", exc)


# ID: e11f1d23-6432-4b99-80a7-b246b5123c50
class CoverageGovernanceCheck(RuleEnforcementCheck):
    """
    Enforces constitutional test coverage requirements.

    Ref: .intent/charter/standards/operations/quality_assurance.json
    """

    policy_rule_ids: ClassVar[list[str]] = [
        "qa.coverage.minimum_threshold",
        "qa.coverage.no_regression",
    ]

    policy_file: ClassVar[Path] = QA_POLICY

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        CoverageMinimumThresholdEnforcement(rule_id="qa.coverage.minimum_threshold"),
        CoverageRegressionEnforcement(rule_id="qa.coverage.no_regression"),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
