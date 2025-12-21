# src/mind/governance/checks/canary_deployment_check.py
"""
Enforces canary deployment rules: abort conditions must be properly configured.

Verifies:
- canary.abort_on_audit_error   — Canary must abort on any audit errors
- canary.abort_on_test_failure  — Canary must abort on any test failures

Ref: .intent/policies/operations/operations.json
"""

from __future__ import annotations

from typing import Any, ClassVar

import yaml

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.config import settings
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: canary-abort-on-audit-error-enforcement
# ID: a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d
class CanaryAbortOnAuditErrorEnforcement(EnforcementMethod):
    """
    Verifies that canary deployment configuration includes abort condition for audit errors.

    This is a meta-check that validates the operations policy intent document itself
    contains the safety rule.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: f9e8d7c6-b5a4-3c2b-1d0e-9f8e7d6c5b4a
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        operations_policy = settings.paths.policy("operations")
        return _verify_abort_rule_in_operations_policy(
            method=self,
            context=context,
            operations_policy=operations_policy,
            rule_id="canary.abort_on_audit_error",
            required_enforcement="error",
            required_metric_substring="audit.errors",
            missing_rule_message=(
                "Missing canary.abort_on_audit_error rule in operations policy - "
                "canary deployments may proceed despite audit failures"
            ),
            metric_hint_message=(
                "canary.abort_on_audit_error rule missing metric specification "
                "(expected something like 'audit.errors == 0')"
            ),
        )


# ID: canary-abort-on-test-failure-enforcement
# ID: 7c2c3a1d-86e8-4c4d-9a0d-2a7f40a7b2f1
class CanaryAbortOnTestFailureEnforcement(EnforcementMethod):
    """
    Verifies that canary deployment configuration includes abort condition for test failures.

    This is a meta-check that validates the operations policy intent document itself
    contains the safety rule.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 4b6b0f3b-3dc1-4e1e-8c2f-6c76f24f9c3c
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        operations_policy = settings.paths.policy("operations")
        return _verify_abort_rule_in_operations_policy(
            method=self,
            context=context,
            operations_policy=operations_policy,
            rule_id="canary.abort_on_test_failure",
            required_enforcement="error",
            required_metric_substring="tests.failures",
            missing_rule_message=(
                "Missing canary.abort_on_test_failure rule in operations policy - "
                "canary deployments may proceed despite failing tests"
            ),
            metric_hint_message=(
                "canary.abort_on_test_failure rule missing metric specification "
                "(expected something like 'tests.failures == 0')"
            ),
        )


def _verify_abort_rule_in_operations_policy(
    *,
    method: EnforcementMethod,
    context: AuditorContext,
    operations_policy,
    rule_id: str,
    required_enforcement: str,
    required_metric_substring: str,
    missing_rule_message: str,
    metric_hint_message: str,
) -> list[AuditFinding]:
    """
    Shared verifier for canary abort rules declared inside the operations policy intent document.

    IMPORTANT:
    - Use EnforcementMethod._create_finding() rather than constructing AuditFinding directly,
      because AuditFinding's constructor signature may differ (as you observed).
    """
    findings: list[AuditFinding] = []

    if not operations_policy.exists():
        findings.append(
            method._create_finding(
                message="Operations policy file missing - canary deployment rules undefined",
                file_path=str(operations_policy.relative_to(context.repo_path)),
            )
        )
        return findings

    try:
        content = operations_policy.read_text(encoding="utf-8")
        data = yaml.safe_load(content) or {}
    except Exception as exc:
        findings.append(
            method._create_finding(
                message=f"Failed to parse operations policy: {exc}",
                file_path=str(operations_policy.relative_to(context.repo_path)),
            )
        )
        return findings

    rules = data.get("rules", [])
    if not isinstance(rules, list):
        findings.append(
            method._create_finding(
                message="Operations policy 'rules' must be a list",
                file_path=str(operations_policy.relative_to(context.repo_path)),
            )
        )
        return findings

    matched: dict[str, Any] | None = None
    for r in rules:
        if isinstance(r, dict) and r.get("id") == rule_id:
            matched = r
            break

    if not matched:
        findings.append(
            method._create_finding(
                message=missing_rule_message,
                file_path=str(operations_policy.relative_to(context.repo_path)),
            )
        )
        return findings

    enforcement = matched.get("enforcement")
    if enforcement != required_enforcement:
        findings.append(
            method._create_finding(
                message=f"{rule_id} has enforcement '{enforcement}' but must be '{required_enforcement}'",
                file_path=str(operations_policy.relative_to(context.repo_path)),
            )
        )

    metric = matched.get("metric")
    metric_str = str(metric) if metric is not None else ""
    if required_metric_substring not in metric_str:
        findings.append(
            method._create_finding(
                message=metric_hint_message,
                file_path=str(operations_policy.relative_to(context.repo_path)),
            )
        )

    return findings


# ID: b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e
class CanaryDeploymentCheck(RuleEnforcementCheck):
    """
    Enforces canary deployment safety rules.

    Ref: .intent/policies/operations/operations.json
    """

    policy_rule_ids: ClassVar[list[str]] = [
        "canary.abort_on_audit_error",
        "canary.abort_on_test_failure",
    ]

    policy_file: ClassVar = settings.paths.policy("operations")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        CanaryAbortOnAuditErrorEnforcement(
            rule_id="canary.abort_on_audit_error",
            severity=AuditSeverity.ERROR,
        ),
        CanaryAbortOnTestFailureEnforcement(
            rule_id="canary.abort_on_test_failure",
            severity=AuditSeverity.ERROR,
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
