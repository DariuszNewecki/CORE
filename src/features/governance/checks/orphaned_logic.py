# src/features/governance/checks/orphaned_logic.py
"""
A constitutional audit check to find "orphaned logic" - public symbols
that have not been assigned a capability ID.
"""
from __future__ import annotations

from typing import Any, Dict, List

from features.governance.audit_context import AuditorContext
from shared.models import AuditFinding, AuditSeverity


# ID: f7064ae9-8396-4e53-b550-f85b482fb2a5
class OrphanedLogicCheck:
    """
    Ensures that all public symbols are assigned a capability, preventing
    undocumented or untracked functionality.
    """

    def __init__(self, context: AuditorContext):
        self.context = context
        self.symbols = self.context.knowledge_graph.get("symbols", {})

    # ID: 92129e3b-c392-41a2-a836-d3e2af32e011
    def find_unassigned_public_symbols(self) -> List[Dict[str, Any]]:
        """Finds all public symbols with a capability of 'unassigned'."""
        unassigned = []
        for symbol_data in self.symbols.values():
            is_public = not symbol_data.get("name", "").startswith("_")
            is_unassigned = symbol_data.get("capability") == "unassigned"
            if is_public and is_unassigned:
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
            findings.append(
                AuditFinding(
                    check_id="capability.assignment.orphaned_logic",
                    severity=AuditSeverity.WARNING,
                    message=f"Public symbol '{symbol['name']}' is not assigned to a capability.",
                    file_path=symbol.get("file"),
                    line_number=symbol.get("line_number"),
                )
            )

        return findings
