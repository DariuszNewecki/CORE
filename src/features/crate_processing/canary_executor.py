# src/features/crate_processing/canary_executor.py

"""
Canary Policy Enforcement.

This module enforces the canary deployment rules defined in
.intent/charter/policies/operations.yaml.

It acts as a bridge between raw runtime signals (AuditFindings, Test Results)
and the constitutional thresholds defined in the Mind.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


@dataclass
# ID: 180cc1c7-60c1-4c69-bce8-3fc77ce12cc9
class CanaryResult:
    """The outcome of a canary check."""

    passed: bool
    violations: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)


# ID: 227aa1c0-77d7-4171-adac-58b6a47959b1
class CanaryExecutor:
    """
    Enforces Canary Policy thresholds.

    Pattern: Stateless Transformer / Validator
    Input: Configuration dict (from operations.yaml)
    Output: CanaryResult
    """

    def __init__(self, canary_config: dict[str, Any]):
        """
        Initialize with the 'canary' section of operations.yaml.

        Args:
            canary_config: Dict containing 'enabled', 'metrics', 'abort_conditions'.
        """
        self.config = canary_config
        self.enabled = self.config.get("enabled", True)

    # ID: 5281cdc8-9cd5-4f32-ba3d-8bd3b2eed8a0
    def derive_metrics_from_audit(
        self, findings: list[AuditFinding]
    ) -> dict[str, float]:
        """
        Convert a list of AuditFindings into quantitative metrics for policy checking.
        """
        error_count = sum(1 for f in findings if f.severity == AuditSeverity.ERROR)
        warning_count = sum(1 for f in findings if f.severity == AuditSeverity.WARNING)
        return {
            "audit.errors": float(error_count),
            "audit.warnings": float(warning_count),
            "audit.findings": float(len(findings)),
        }

    # ID: 2a89880e-9157-4a36-8b47-e1e13a54becd
    def enforce(self, runtime_metrics: dict[str, float]) -> CanaryResult:
        """
        Compare runtime metrics against policy thresholds.

        Args:
            runtime_metrics: Dictionary of metric_name -> value
                             (e.g., {"audit.errors": 0, "tests.failed": 0})

        Returns:
            CanaryResult: Pass/Fail status with details.
        """
        if not self.enabled:
            logger.info("Canary checks disabled in policy.")
            return CanaryResult(True, [], runtime_metrics)
        violations = []
        policy_metrics = self.config.get("metrics", [])
        for rule in policy_metrics:
            metric_name = rule["name"]
            threshold = float(rule["threshold"])
            direction = rule.get("direction", "less")
            actual_value = runtime_metrics.get(metric_name)
            if actual_value is None:
                logger.debug(
                    "Canary metric '%s' not present in runtime report.", metric_name
                )
                continue
            if direction == "less":
                if actual_value > threshold:
                    violations.append(
                        f"Metric '{metric_name}' failed: {actual_value} > {threshold}"
                    )
            elif direction == "greater":
                if actual_value < threshold:
                    violations.append(
                        f"Metric '{metric_name}' failed: {actual_value} < {threshold}"
                    )
        abort_conditions = self.config.get("abort_conditions", [])
        for condition in abort_conditions:
            if condition == "audit:level=error":
                if runtime_metrics.get("audit.errors", 0) > 0:
                    violations.append("Abort condition triggered: audit:level=error")
            elif condition == "tests:failed>0":
                if runtime_metrics.get("tests.failed", 0) > 0:
                    violations.append("Abort condition triggered: tests:failed>0")
        passed = len(violations) == 0
        if not passed:
            logger.warning("Canary checks failed: %s", violations)
        else:
            logger.info("Canary checks passed.")
        return CanaryResult(passed, violations, runtime_metrics)
