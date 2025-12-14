# src/mind/governance/checks/coverage_check.py
"""
Constitutional enforcement of test coverage requirements.
Verifies compliance with 'coverage.minimum_threshold' and 'coverage.no_untested_commits'.
"""

from __future__ import annotations

import json
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 365e9a78-c99e-4b36-82a8-6a1ba5e08fd4
class CoverageGovernanceCheck(BaseCheck):
    """
    Enforces constitutional test coverage requirements.
    Ref: standard_operations_quality_assurance
    """

    policy_rule_ids = [
        "coverage.minimum_threshold",
        "coverage.no_untested_commits",
    ]

    def __init__(self, context: AuditorContext) -> None:
        super().__init__(context)
        # Load SSOT from Context
        policy = self.context.policies.get("quality_assurance", {})
        coverage_cfg = policy.get("coverage_requirements", {})

        self.minimum_threshold: float = float(
            coverage_cfg.get("minimum_threshold", 75.0)
        )
        self.critical_paths: list[str] = coverage_cfg.get("critical_paths", [])
        self.exclusions: list[str] = coverage_cfg.get("exclusions", [])

    # ID: e11f1d23-6432-4b99-80a7-b246b5123c50
    async def execute(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        coverage_data = self._measure_coverage()

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
                AuditFinding(
                    check_id="coverage.minimum_threshold",
                    severity=AuditSeverity.ERROR,
                    message=(
                        f"Coverage {overall_coverage}% is below constitutional minimum "
                        f"of {self.minimum_threshold}%."
                    ),
                    file_path="coverage.json",
                    context={
                        "current": overall_coverage,
                        "required": self.minimum_threshold,
                        "delta": overall_coverage - self.minimum_threshold,
                    },
                )
            )

        # 2) Enforce Critical Paths
        for path_spec in self.critical_paths:
            path_pattern, required = self._parse_path_spec(path_spec)
            actual = self._get_path_coverage(coverage_data, path_pattern)

            if actual is not None and actual < required:
                findings.append(
                    AuditFinding(
                        check_id="coverage.minimum_threshold.critical_path",
                        severity=AuditSeverity.ERROR,
                        message=(
                            f"Critical path '{path_pattern}' coverage {actual}% "
                            f"below required {required}%."
                        ),
                        file_path=path_pattern,
                        context={
                            "current": actual,
                            "required": required,
                            "delta": actual - required,
                        },
                    )
                )

        # 3) Enforce Regression
        regression = self._check_regression(coverage_data)
        if regression:
            findings.append(regression)

        return findings

    def _measure_coverage(self) -> dict[str, Any] | None:
        """Loads coverage data from coverage.json (produced by pytest-cov)."""
        coverage_json = self.repo_root / "coverage.json"

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

    def _check_regression(self, coverage_data: dict[str, Any]) -> AuditFinding | None:
        """Checks if coverage has dropped significantly (>5%) since last run."""
        history_file = self.repo_root / ".intent/mind/history/coverage_history.json"

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
                    return AuditFinding(
                        check_id="coverage.no_untested_commits",
                        severity=AuditSeverity.ERROR,
                        message=f"Significant coverage regression: {abs(delta):.1f}% drop.",
                        file_path="N/A",
                        context={"previous": last_percent, "current": current_percent},
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
