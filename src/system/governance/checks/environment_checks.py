# src/system/governance/checks/environment_checks.py
"""
Audits the system's runtime environment for required configuration and environment variables.
"""

from __future__ import annotations

# src/system/governance/checks/environment_checks.py
"""Auditor checks related to the system's runtime environment."""
import os

from system.governance.models import AuditFinding, AuditSeverity


class EnvironmentChecks:
    """Container for environment and runtime configuration checks."""

    def __init__(self, context):
        """Initializes the check with a shared auditor context."""
        self.context = context

    # CAPABILITY: audit.check.environment
    def check_runtime_environment(self) -> list[AuditFinding]:
        """Verifies that required environment variables specified in runtime_requirements.yaml are set, returning a list of audit findings for missing variables or configuration issues."""
        """Verifies that required environment variables are set."""
        findings = []
        check_name = "Runtime Environment Validation"

        requirements_path = (
            self.context.intent_dir / "config" / "runtime_requirements.yaml"
        )
        if not requirements_path.exists():
            findings.append(
                AuditFinding(
                    AuditSeverity.WARNING,
                    "runtime_requirements.yaml not found; cannot validate environment.",
                    check_name,
                )
            )
            return findings

        requirements = self.context.load_config(requirements_path, "yaml")
        required_vars = requirements.get("required_environment_variables", [])

        missing_vars = []
        for var in required_vars:
            if var.get("required") and not os.getenv(var.get("name")):
                missing_vars.append(var)

        if missing_vars:
            for var in missing_vars:
                msg = f"Required environment variable '{var.get('name')}' is not set. Description: {var.get('description')}"
                findings.append(AuditFinding(AuditSeverity.ERROR, msg, check_name))
        else:
            findings.append(
                AuditFinding(
                    AuditSeverity.SUCCESS,
                    "All required environment variables are set.",
                    check_name,
                )
            )

        return findings
