# src/mind/governance/checks/environment_checks.py
"""
Audits the system's runtime environment for required configuration, enforcing
the 'operations.runtime.env_vars_defined' constitutional rule.
"""

from __future__ import annotations

import os
from typing import Any

from shared.models import AuditFinding, AuditSeverity

# No longer need 'Any' as we know the context type
from mind.governance.audit_context import AuditorContext
from mind.governance.checks.base_check import BaseCheck


# ID: 0c3965b7-b3f3-4fb6-bbbb-c94a1ffae3fe
class EnvironmentChecks(BaseCheck):
    """
    Ensures that all constitutionally required environment variables are set
    at runtime, as defined in the 'runtime_requirements' policy.
    """

    # Fulfills the contract from BaseCheck, linking this operational check
    # to the core constitution.
    policy_rule_ids = ["operations.runtime.env_vars_defined"]

    def __init__(self, context: AuditorContext) -> None:
        super().__init__(context)
        # This check is governed by the 'runtime_requirements' policy, which
        # should be loaded into the central context.
        self.requirements: dict[str, Any] = self.context.policies.get(
            "runtime_requirements", {}
        )

    # ID: 0c0e7695-b11e-4ad8-9e74-23d5f79dad00
    def execute(self) -> list[AuditFinding]:
        """
        Verifies that required environment variables are set.
        """
        findings: list[AuditFinding] = []

        required_vars = self.requirements.get("variables", {})
        if not isinstance(required_vars, dict):
            findings.append(
                AuditFinding(
                    # This check_id indicates a misconfiguration of the policy
                    # this check depends on.
                    check_id="operations.runtime.policy_misconfigured",
                    severity=AuditSeverity.ERROR,
                    message=(
                        "runtime_requirements.variables must be a mapping of "
                        "ENV_VAR_NAME -> config dict."
                    ),
                    file_path="mind/runtime_requirements.yaml",
                )
            )
            return findings

        for name, config in required_vars.items():
            if not isinstance(config, dict) or not config.get("required"):
                continue

            if not os.getenv(name):
                description = config.get("description", "No description provided.")
                message = (
                    f"Required environment variable '{name}' is not set. "
                    f"Description: {description}"
                )
                findings.append(
                    AuditFinding(
                        # The finding directly references the constitutional rule.
                        check_id="operations.runtime.env_vars_defined",
                        severity=AuditSeverity.ERROR,
                        message=message,
                        file_path=".env",  # Hint to human where to fix it
                        context={"variable_name": name},
                    )
                )

        return findings
