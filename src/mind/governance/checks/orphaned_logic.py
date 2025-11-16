# src/mind/governance/checks/orphaned_logic.py
"""
A constitutional audit check to find "orphaned logic" - public symbols
that have not been assigned a capability, enforcing the 'intent_alignment' rule.
"""

from __future__ import annotations

import re
from typing import Any

from shared.models import AuditFinding, AuditSeverity

from mind.governance.audit_context import AuditorContext

# Import the BaseCheck to inherit from it
from mind.governance.checks.base_check import BaseCheck


# ID: bc44f537-758e-49a2-9914-fc6355b51f48
# Inherit from BaseCheck
# ID: dfed0c32-d0d3-487b-8154-40b247c8a0bb
class OrphanedLogicCheck(BaseCheck):
    """
    Ensures that all public symbols are assigned to a capability, enforcing
    the 'intent_alignment' rule by preventing undocumented functionality.
    """

    # Fulfills the contract from BaseCheck.
    policy_rule_ids = ["intent_alignment"]

    def __init__(self, context: AuditorContext):
        super().__init__(context)
        self.symbols = self.context.symbols_map

        # --- Centralized Configuration ---
        # All required policies are retrieved from the single context object.
        # The check is no longer responsible for loading files.
        ignore_policy = self.context.policies.get("audit_ignore_policy", {})
        structure_policy = self.context.policies.get("project_structure", {})

        self.ignored_symbol_keys = {
            item["key"]
            for item in ignore_policy.get("symbol_ignores", [])
            if "key" in item
        }
        self.entry_point_patterns = structure_policy.get("entry_point_patterns", [])

    def _is_entry_point(self, symbol_data: dict[str, Any]) -> bool:
        """Checks if a symbol matches any of the defined entry point patterns."""
        for pattern in self.entry_point_patterns:
            match_rules = pattern.get("match", {})
            # Assume it's a match until a rule fails
            is_a_match = all(
                self._evaluate_match_rule(rule_key, rule_value, symbol_data)
                for rule_key, rule_value in match_rules.items()
            )
            if is_a_match:
                return True
        return False

    def _evaluate_match_rule(self, key: str, value: Any, data: dict) -> bool:
        """Evaluates a single criterion for the entry point pattern matching."""
        if key == "type":
            is_class = data.get("is_class", False)
            return (value == "class" and is_class) or (
                value == "function" and not is_class
            )
        if key == "name_regex":
            return bool(re.search(value, data.get("name", "")))
        if key == "module_path_contains":
            return value in data.get("file_path", "")
        # Add other rule evaluations here if needed
        return data.get(key) == value

    # ID: 567318b3-2e45-4383-8af6-9880c3c9576c
    def _find_unassigned_public_symbols(self) -> list[dict[str, Any]]:
        """Finds all public symbols with a null capability key that are not ignored."""
        unassigned = []
        for symbol_key, symbol_data in self.symbols.items():
            is_public = not symbol_data.get("name", "").startswith("_")
            is_unassigned = symbol_data.get("capability") is None
            is_ignored = symbol_key in self.ignored_symbol_keys

            if is_public and is_unassigned and not is_ignored:
                if not self._is_entry_point(symbol_data):
                    symbol_data["key"] = symbol_key
                    unassigned.append(symbol_data)
        return unassigned

    # ID: 2ba01327-4559-427f-b0d4-a0737b7937fc
    def execute(self) -> list[AuditFinding]:
        """
        Runs the check and returns a list of findings for any orphaned symbols.
        """
        findings = []
        orphaned_symbols = self._find_unassigned_public_symbols()

        for symbol in orphaned_symbols:
            symbol_key = symbol.get("key", "unknown")
            short_name = symbol_key.split("::")[-1]

            findings.append(
                AuditFinding(
                    # The check_id now matches the constitution.
                    check_id="intent_alignment",
                    severity=AuditSeverity.ERROR,
                    message=f"Orphaned logic found: Public symbol '{short_name}' is not assigned to a capability.",
                    file_path=symbol.get("file_path"),
                    line_number=symbol.get("line_number"),
                    context={"symbol_key": symbol_key},
                )
            )
        return findings
