# src/mind/governance/checks/manifest_lint.py
"""
Audits capability definitions (docstrings) for quality issues.
Enforces caps.no_placeholder_text: Docstrings must be meaningful.
"""

from __future__ import annotations

import re

from mind.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# Regex for word-boundary matching to avoid false positives (e.g. "outbdated")
# Matches: Start of string or whitespace + term + whitespace or end of string/punctuation
PLACEHOLDER_PATTERNS = [
    re.compile(r"\bTBD\b", re.IGNORECASE),
    re.compile(r"\bN/A\b", re.IGNORECASE),
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"\bAUTO-ADDED\b", re.IGNORECASE),
    re.compile(r"\bPLACEHOLDER\b", re.IGNORECASE),
]


# ID: ee190b8d-1bf0-4b1a-90e2-abf21ca013c9
class ManifestLintCheck(BaseCheck):
    """
    Checks for placeholder text in capability descriptions (docstrings).
    Ref: standard_code_general (caps.no_placeholder_text)
    """

    policy_rule_ids = [
        "caps.no_placeholder_text",
        "caps.meaningful_description",
    ]

    # ID: 2e114e07-e521-4e56-a56c-f3afc6458f44
    def execute(self) -> list[AuditFinding]:
        """Finds capabilities with placeholder descriptions."""
        findings = []

        for symbol in self.context.symbols_list:
            # Skip private helpers (they don't need formal descriptions per policy)
            # Ref: symbols.private_helpers_no_id_required
            if symbol.get("name", "").startswith("_"):
                continue

            # "intent" in knowledge graph maps to the docstring/description
            description = (symbol.get("intent", "") or "").strip()

            # 1. Check for Empty Description (Meaningful Description Rule)
            if not description:
                # Only strictly enforce this on symbols that HAVE a capability ID
                # (Verified by IdCoverageCheck, but double check here contextually if needed)
                if symbol.get("capability_id"):
                    findings.append(
                        AuditFinding(
                            check_id="caps.meaningful_description",
                            severity=AuditSeverity.ERROR,
                            message=f"Public capability '{symbol.get('name')}' is missing a description.",
                            file_path=symbol.get("file_path"),
                            line_number=symbol.get("line_number"),
                        )
                    )
                continue

            # 2. Check for Placeholders
            for pattern in PLACEHOLDER_PATTERNS:
                if pattern.search(description):
                    findings.append(
                        AuditFinding(
                            check_id="caps.no_placeholder_text",
                            severity=AuditSeverity.ERROR,
                            message=(
                                f"Capability '{symbol.get('name')}' contains forbidden placeholder text: "
                                f"'{pattern.pattern}'"
                            ),
                            file_path=symbol.get("file_path"),
                            line_number=symbol.get("line_number"),
                            context={"current_description": description},
                        )
                    )
                    break  # One violation is enough

        return findings
