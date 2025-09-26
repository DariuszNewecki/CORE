# src/features/governance/checks/environment_checks.py
"""
Audits the system's runtime environment for required configuration.
"""
from __future__ import annotations

import os

from features.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: 0c3965b7-b3f3-4fb6-bbbb-c94a1ffae3fe
class EnvironmentChecks(BaseCheck):
    """Container for environment and runtime configuration checks."""

    def __init__(self, context):
        super().__init__(context)
        self.requirements = self.context.policies.get("runtime_requirements", {})

    # ID: 0c0e7695-b11e-4ad8-9e74-23d5f79dad00
    def execute(self) -> list[AuditFinding]:
        """
        Verifies that required environment variables specified in
        runtime_requirements.yaml are set.
        """
        findings = []
        required_vars = self.requirements.get("variables", {})

        for name, config in required_vars.items():
            if config.get("required") and not os.getenv(name):
                msg = (
                    f"Required environment variable '{name}' is not set. "
                    f"Description: {config.get('description', 'No description.')}"
                )
                findings.append(
                    AuditFinding(
                        check_id="environment.variable.missing",
                        severity=AuditSeverity.ERROR,
                        message=msg,
                        file_path=".env",
                    )
                )
        return findings
