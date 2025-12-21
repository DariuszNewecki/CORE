# src/mind/governance/checks/environment_checks.py
"""
Audits the system's runtime environment for required configuration.
Enforces 'operations.runtime.env_vars_defined' with support for conditional requirements.
"""

from __future__ import annotations

import os
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 0c3965b7-b3f3-4fb6-bbbb-c94a1ffae3fe
class EnvironmentChecks(BaseCheck):
    """
    Ensures that all constitutionally required environment variables are set.
    Respects 'required_when' conditions to support different runtime modes (e.g., Local vs Prod).
    """

    policy_rule_ids: ClassVar[list[str]] = ["operations.runtime.env_vars_defined"]

    def __init__(self, context: AuditorContext) -> None:
        super().__init__(context)
        self.requirements: dict[str, Any] = self.context.policies.get(
            "runtime_requirements", {}
        )

    # ID: 0c0e7695-b11e-4ad8-9e74-23d5f79dad00
    def execute(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        required_vars = self.requirements.get("variables", {})
        if not isinstance(required_vars, dict):
            # Fail gracefully if schema is wrong, but report it
            findings.append(
                AuditFinding(
                    check_id="operations.runtime.policy_misconfigured",
                    severity=AuditSeverity.ERROR,
                    message="runtime_requirements.variables must be a dict.",
                    file_path=".intent/mind/config/runtime_requirements.yaml",
                )
            )
            return findings

        for name, config in required_vars.items():
            if not isinstance(config, dict):
                continue

            # 1. Basic Requirement Check
            is_required = config.get("required", False)

            # 2. Conditional Requirement Check (Context Awareness)
            # If required_when is present, it overrides the base 'required' flag logic
            if "required_when" in config:
                is_required = self._evaluate_condition(config["required_when"])

            if not is_required:
                continue

            # 3. Validation
            if not os.getenv(name):
                # Check for default value in config as fallback
                if "default" in config:
                    continue

                desc = config.get("description", "No description provided.")
                findings.append(
                    AuditFinding(
                        check_id="operations.runtime.env_vars_defined",
                        severity=AuditSeverity.ERROR,
                        message=f"Missing Runtime Variable: '{name}'. {desc}",
                        file_path=".env",
                        context={
                            "variable": name,
                            "condition": config.get("required_when"),
                        },
                    )
                )

        return findings

    def _evaluate_condition(self, condition: str) -> bool:
        """
        Evaluates simple 'VAR == value' conditions against current environment.
        Used for toggles like 'LLM_ENABLED == true'.
        """
        try:
            # Simple parser for "KEY == value"
            if "==" in condition:
                key, val = (x.strip() for x in condition.split("==", 1))
                # Normalize string booleans
                env_val = str(os.getenv(key, "")).lower()
                target_val = val.lower().replace('"', "").replace("'", "")
                return env_val == target_val

            # Simple parser for "KEY != value"
            if "!=" in condition:
                key, val = (x.strip() for x in condition.split("!=", 1))
                env_val = str(os.getenv(key, "")).lower()
                target_val = val.lower().replace('"', "").replace("'", "")
                return env_val != target_val

            logger.warning("Unsupported condition format: '%s'", condition)
            return True  # Fail safe (assume required) if we can't parse

        except Exception as e:
            logger.error("Error evaluating condition '%s': %s", condition, e)
            return True
