# src/features/governance/checks/orphaned_logic.py
"""
A constitutional audit check to find "orphaned logic" - public symbols
that have not been assigned a capability ID in the database.
"""

from __future__ import annotations

import re
from typing import Any

from features.governance.audit_context import AuditorContext
from shared.config import settings
from shared.models import AuditFinding, AuditSeverity


# ID: f7064ae9-8396-4e53-b550-f85b482fb2a5
class OrphanedLogicCheck:
    """
    Ensures that all public symbols are assigned a capability, preventing
    undocumented or untracked functionality. This check respects the
    `audit_ignore_policy.yaml` and the new `entry_point_patterns.yaml`.
    """

    def __init__(self, context: AuditorContext):
        self.context = context
        self.symbols = self.context.symbols_map

        ignore_policy = self.context.policies.get("audit_ignore_policy", {})
        self.ignored_symbol_keys = {
            item["key"]
            for item in ignore_policy.get("symbol_ignores", [])
            if "key" in item
        }
        self.entry_point_patterns = settings.load(
            "mind.knowledge.entry_point_patterns"
        ).get("patterns", [])

    def _is_entry_point(self, symbol_data: dict[str, Any]) -> bool:
        """Checks if a symbol matches any of the defined entry point patterns."""
        for pattern in self.entry_point_patterns:
            match_rules = pattern.get("match", {})
            is_match = True
            for rule_key, rule_value in match_rules.items():
                # NOTE: This implementation is resilient. It only checks for keys
                # that are guaranteed to be in the symbol_data from the DB view.
                # If the DB schema is extended later (e.g., with 'base_classes'),
                # this check will automatically start using it without code changes.
                symbol_value = symbol_data.get(rule_key)

                if rule_key == "type":
                    is_class = symbol_data.get("is_class", False)
                    if (rule_value == "class" and not is_class) or (
                        rule_value == "function" and is_class
                    ):
                        is_match = False
                        break
                elif rule_key == "name_regex":
                    if not re.search(rule_value, symbol_data.get("name", "")):
                        is_match = False
                        break
                elif rule_key == "module_path_contains":
                    if rule_value not in symbol_data.get("file_path", ""):
                        is_match = False
                        break
                elif rule_key == "has_capability_tag":
                    if rule_value and not symbol_data.get("capability"):
                        is_match = False
                        break
                elif rule_key == "is_public_function":
                    if rule_value and symbol_data.get("name", "").startswith("_"):
                        is_match = False
                        break
                # Safely ignore rules we can't check, like 'base_class_includes' for now
                elif symbol_value is None:
                    is_match = False
                    break
            if is_match:
                return True
        return False

    # ID: 92129e3b-c392-41a2-a836-d3e2af32e011
    def find_unassigned_public_symbols(self) -> list[dict[str, Any]]:
        """Finds all public symbols with a null capability key that are not ignored."""
        unassigned = []
        for symbol_key, symbol_data in self.symbols.items():
            is_public = symbol_data.get("is_public", False)
            is_unassigned = symbol_data.get("capability") is None
            is_ignored = symbol_key in self.ignored_symbol_keys
            is_entry_point = self._is_entry_point(symbol_data)

            if is_public and is_unassigned and not is_ignored and not is_entry_point:
                symbol_data["key"] = symbol_key
                unassigned.append(symbol_data)
        return unassigned

    # ID: f7903b52-27f9-44e2-b3b5-5d0d90c5e949
    def execute(self) -> list[AuditFinding]:
        """
        Runs the check and returns a list of findings for any orphaned symbols.
        """
        findings = []
        orphaned_symbols = self.find_unassigned_public_symbols()

        for symbol in orphaned_symbols:
            symbol_key = symbol.get("key", "unknown")
            short_name = symbol_key.split("::")[-1]

            findings.append(
                AuditFinding(
                    check_id="linkage.capability.unassigned",
                    severity=AuditSeverity.ERROR,
                    message=f"Public symbol '{short_name}' is not assigned to a capability in the database.",
                    file_path=symbol.get("file_path"),
                    line_number=symbol.get("line_number"),
                    context={"symbol_key": symbol_key},
                )
            )

        return findings
