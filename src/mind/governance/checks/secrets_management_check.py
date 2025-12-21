# src/mind/governance/checks/secrets_management_check.py
# ID: model.mind.governance.checks.secrets_management_check
"""
Constitutional check for Secrets Management rules.

Uses RuleEnforcementCheck template to verify:
- secrets.no_raw_access
- secrets.provider_abstraction
- secrets.rotation_autonomy

Ref: .intent/charter/standards/operations/secrets_management.json
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from mind.governance.checks.rule_enforcement_check import RuleEnforcementCheck
from mind.governance.enforcement_methods import CodePatternEnforcement


SECRETS_POLICY_FILE = Path(
    ".intent/charter/standards/operations/secrets_management.json"
)


# ID: secrets-management-check
# ID: bda653fb-3ddc-4719-bcc5-e760ecae87b3
class SecretsManagementCheck(RuleEnforcementCheck):
    """
    Verifies that secrets are managed according to constitutional standards.
    Ref: .intent/charter/standards/operations/secrets_management.json
    """

    # Standardized binding: this concrete check declares which rules it enforces.
    policy_rule_ids: ClassVar[list[str]] = [
        "secrets.no_raw_access",
        "secrets.provider_abstraction",
        "secrets.rotation_autonomy",
    ]
    id: ClassVar[str] = "secrets_management"

    policy_file: ClassVar[Path] = SECRETS_POLICY_FILE

    enforcement_methods: ClassVar[list] = [
        # 1) No raw environment access:
        # These patterns represent direct env access mechanisms that must be flagged.
        CodePatternEnforcement(
            rule_id="secrets.no_raw_access",
            required_patterns=[
                r"os\.environ\[",
                r"os\.environ\.get\(",
                r"os\.getenv\(",
            ],
        ),
        # 2) Provider abstraction must exist in the codebase usage:
        # This pattern represents the expected abstraction being used (positive signal).
        CodePatternEnforcement(
            rule_id="secrets.provider_abstraction",
            required_patterns=[
                r"SecretProvider",
            ],
        ),
        # 3) Rotation autonomy:
        # These patterns represent hardcoded secret assignments that must be flagged.
        CodePatternEnforcement(
            rule_id="secrets.rotation_autonomy",
            required_patterns=[
                r"API_KEY\s*=\s*[\"']",
                r"SECRET\s*=\s*[\"']",
                r"PASSWORD\s*=\s*[\"']",
            ],
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
