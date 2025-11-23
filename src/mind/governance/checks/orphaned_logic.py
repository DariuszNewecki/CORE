# src/mind/governance/checks/orphaned_logic.py
"""
A constitutional audit check to find "orphaned logic" - public symbols
that have not been assigned a capability, enforcing the 'intent_alignment' rule.
"""

from __future__ import annotations

import re
from typing import Any

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: 83663760-524c-4698-b77c-05a8883d9067
class OrphanedLogicCheck(BaseCheck):
    """
    Ensures that all public symbols are assigned to a capability, enforcing
    the 'intent_alignment' rule by preventing undocumented functionality.
    A symbol is considered an orphan if it is public, un-keyed, not a designated
    entry point, AND has no incoming calls from any other symbol.
    """

    policy_rule_ids = ["intent_alignment"]

    def __init__(self, context: AuditorContext):
        super().__init__(context)
        # The symbols_list is pre-loaded by the AuditorContext from the knowledge_graph VIEW
        self.all_symbols = self.context.symbols_list
        # FIX: Load from source_structure instead of policies
        self.entry_point_patterns = self.context.source_structure.get(
            "entry_point_patterns", []
        )

    def _is_entry_point(self, symbol_data: dict[str, Any]) -> bool:
        """Checks if a symbol matches any of the defined entry point patterns."""
        for pattern in self.entry_point_patterns:
            match_rules = pattern.get("match", {})
            if not match_rules:
                continue
            is_a_match = all(
                self._evaluate_match_rule(rule_key, rule_value, symbol_data)
                for rule_key, rule_value in match_rules.items()
            )
            if is_a_match:
                return True
        return False

    def _evaluate_match_rule(self, key: str, value: Any, data: dict) -> bool:
        """Evaluates a single criterion for the entry point pattern matching."""
        # --- START OF FIX: Use the correct column names from the VIEW ---
        if key == "type":
            # The view aliases 'kind' to 'type'
            kind = data.get("type", "")
            is_function_type = kind in ("function", "method")
            return (value == "function" and is_function_type) or (value == kind)
        if key == "name_regex":
            # The view aliases 'qualname' to 'name'
            return bool(re.search(value, data.get("name", "")))
        if key == "module_path_contains":
            # The view aliases 'module' to 'file_path', but we should check against the Python module path
            # which is still present in the underlying table, so we use 'module' from the context.
            # However, for consistency with the view, let's assume we need to adapt.
            # Let's derive the module from file_path.
            file_path = data.get("file_path", "")
            module_path = (
                file_path.replace("src/", "").replace(".py", "").replace("/", ".")
            )
            return value in module_path
        if key == "is_public_function":
            return data.get("is_public", False) is value
        if key == "has_capability_tag":
            # The view aliases 'key' to 'capability'
            return (data.get("capability") is not None) == value
        # --- END OF FIX ---
        return data.get(key) == value

    # ID: d7ea188f-280a-4ac1-ac98-ca0403e33291
    def execute(self) -> list[AuditFinding]:
        """
        Runs the check and returns a list of findings for any truly orphaned symbols.
        """
        findings = []

        if not self.all_symbols:
            return findings

        all_called_symbols = set()
        for symbol_data in self.all_symbols:
            called_list = symbol_data.get("calls") or []
            for called_qualname in called_list:
                all_called_symbols.add(called_qualname)

        orphaned_symbols = []
        for symbol_data in self.all_symbols:
            is_public = symbol_data.get("is_public", False)
            # The view aliases 'key' to 'capability'
            has_no_key = symbol_data.get("capability") is None

            if not (is_public and has_no_key):
                continue

            if self._is_entry_point(symbol_data):
                continue

            # The view aliases 'qualname' to 'name'
            qualname = symbol_data.get("name", "")
            short_name = qualname.split(".")[-1]
            is_called = (qualname in all_called_symbols) or (
                short_name in all_called_symbols
            )

            if not is_called:
                orphaned_symbols.append(symbol_data)

        for symbol in orphaned_symbols:
            symbol_path = symbol.get("symbol_path", "unknown")
            # The view aliases 'qualname' to 'name'
            short_name = symbol.get("name", "unknown")

            findings.append(
                AuditFinding(
                    check_id="intent_alignment",
                    severity=AuditSeverity.ERROR,
                    message=f"Orphaned logic found: Public symbol '{short_name}' is not an entry point, is not called by any other code, and has no assigned capability.",
                    file_path=symbol.get("file_path", ""),
                )
            )

        return findings
