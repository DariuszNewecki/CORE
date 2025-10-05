# src/features/governance/checks/orphaned_logic.py
"""
A constitutional audit check to find "orphaned logic" - public symbols
that have not been assigned a capability ID in the database.
"""

from __future__ import annotations

from typing import Any, Dict, List

from shared.models import AuditFinding, AuditSeverity

from features.governance.audit_context import AuditorContext


# ID: f7064ae9-8396-4e53-b550-f85b482fb2a5
class OrphanedLogicCheck:
    """
    Ensures that all public symbols are assigned a capability, preventing
    undocumented or untracked functionality. This check respects the
    `audit_ignore_policy.yaml`.
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

    # ID: 92129e3b-c392-41a2-a836-d3e2af32e011
    def find_unassigned_public_symbols(self) -> List[Dict[str, Any]]:
        """Finds all public symbols with a null capability key that are not ignored."""
        unassigned = []
        for symbol_key, symbol_data in self.symbols.items():
            is_public = symbol_data.get("is_public", False)
            # A symbol is unassigned if its 'capability' (the key) is null.
            is_unassigned = symbol_data.get("capability") is None
            is_ignored = symbol_key in self.ignored_symbol_keys

            if is_public and is_unassigned and not is_ignored:
                # Add the canonical key to the dict for the finding
                symbol_data["key"] = symbol_key
                unassigned.append(symbol_data)
        return unassigned

    # ID: f7903b52-27f9-44e2-b3b5-5d0d90c5e949
    def execute(self) -> List[AuditFinding]:
        """
        Runs the check and returns a list of findings for any orphaned symbols.
        """
        findings = []
        orphaned_symbols = self.find_unassigned_public_symbols()

        for symbol in orphaned_symbols:
            # Use the canonical key from the symbol data for the message
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
