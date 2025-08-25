# src/system/governance/checks/architecture_checks.py
"""
Audits codebase architecture for structural duplication and other high-level design violations.
"""

from __future__ import annotations

from collections import defaultdict

from system.governance.models import AuditFinding, AuditSeverity


class ArchitectureChecks:
    """Container for architectural integrity checks."""

    def __init__(self, context):
        """Initializes the check with a shared auditor context."""
        self.context = context

    # CAPABILITY: audit.check.duplication
    def check_for_structural_duplication(self) -> list[AuditFinding]:
        """Finds symbols with identical structural hashes, violating `dry_by_design`, using content-addressed knowledge graph for accurate duplication detection."""
        """
        Finds symbols with identical structural hashes, violating `dry_by_design`.
        This check uses the content-addressed nature of the knowledge graph to
        detect code duplication with perfect accuracy.
        """
        findings = []
        check_name = "Architectural Integrity: Code Duplication"

        hashes = defaultdict(list)
        for symbol in self.context.symbols_list:
            # We only care about functions and classes, not their methods for now.
            if symbol.get("structural_hash") and not symbol.get("parent_class_key"):
                hashes[symbol["structural_hash"]].append(symbol["key"])

        duplicates_found = False
        for structural_hash, keys in hashes.items():
            if len(keys) > 1:
                duplicates_found = True
                locations = ", ".join(f"'{key}'" for key in keys)
                message = (
                    f"Structural duplication detected. The following symbols are "
                    f"identical: {locations}. This may violate the 'dry_by_design' principle."
                )
                findings.append(
                    AuditFinding(AuditSeverity.WARNING, message, check_name)
                )

        # --- THIS IS THE FIX ---
        # We explicitly add a success message to the findings list if no duplicates are found.
        if not duplicates_found:
            findings.append(
                AuditFinding(
                    AuditSeverity.SUCCESS,
                    "No structural code duplication found.",
                    check_name,
                )
            )

        return findings
