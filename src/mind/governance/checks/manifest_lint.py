# src/mind/governance/checks/manifest_lint.py
"""
Audits capability manifests for quality issues like placeholder text, enforcing
the 'caps.no_placeholder_text' and 'caps.meaningful_description' rules.
"""

from __future__ import annotations

from mind.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# Define placeholder strings as a constant for clarity.
# In the future, this could be loaded from the policy file itself.
PLACEHOLDER_SUBSTRINGS = {"tbd", "n/a", "auto-added"}


# ID: ee190b8d-1bf0-4b1a-90e2-abf21ca013c9
class ManifestLintCheck(BaseCheck):
    """
    Checks for placeholder text in capability manifest descriptions to ensure
    all documented capabilities are meaningful.
    """

    # Fulfills the contract from BaseCheck. This check enforces two related
    # rules from the code_standards policy.
    policy_rule_ids = [
        "caps.no_placeholder_text",
        "caps.meaningful_description",
    ]

    # The __init__ is no longer needed; we can get the symbols list
    # directly from self.context in the execute method.

    # ID: 2e114e07-e521-4e56-a56c-f3afc6458f44
    def execute(self) -> list[AuditFinding]:
        """Finds capabilities with placeholder descriptions."""
        findings = []

        # The check's logic is self-contained and doesn't need to load the rule
        # from the policy, as its purpose is to enforce this specific behavior.

        for symbol in self.context.symbols_list:
            # A symbol's "intent" is its description in the manifest.
            description = (symbol.get("intent", "") or "").lower()

            if any(p in description for p in PLACEHOLDER_SUBSTRINGS):
                original_description = symbol.get("intent", "") or ""
                findings.append(
                    AuditFinding(
                        # The check_id now matches the specific constitutional rule.
                        check_id="caps.no_placeholder_text",
                        # The severity now matches the policy's 'error' enforcement.
                        severity=AuditSeverity.ERROR,
                        message=(
                            f"Capability '{symbol.get('key')}' has a forbidden placeholder "
                            f"description: '{original_description}'"
                        ),
                        file_path=symbol.get("file_path"),
                        line_number=symbol.get("line_number"),
                    )
                )
        return findings
