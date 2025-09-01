# src/system/governance/checks/environment_checks.py
"""
Audits the system's runtime environment for required configuration and environment variables.
"""

from __future__ import annotations

import os

from system.governance.models import AuditFinding, AuditSeverity


# CAPABILITY: audit.check.environment_configuration
class EnvironmentChecks:
    """Container for environment and runtime configuration checks."""

    # CAPABILITY: audit.check.environment.initialize
    def __init__(self, context):
        """Initializes the check with a shared auditor context."""
        self.context = context

    # CAPABILITY: audit.check.environment
    def check_runtime_environment(self) -> list[AuditFinding]:
        """Verifies that required environment variables specified in runtime_requirements.yaml are set, returning a list of audit findings for missing variables or configuration issues."""
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

        requirements = self.context.load_config(requirements_path)
        # The new structure is a map under the 'variables' key.
        required_vars = requirements.get("variables", {})

        missing_vars = []
        for name, config in required_vars.items():
            # Check if required is true and the env var is not set.
            if config.get("required") and not os.getenv(name):
                # Also pass along the description for a better error message.
                missing_vars.append(
                    {
                        "name": name,
                        "description": config.get("description", "No description."),
                    }
                )

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
