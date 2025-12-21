# src/mind/governance/checks/manifest_lint.py
"""
Audits capability definitions (docstrings) for quality issues.
Enforces caps.no_placeholder_text: Docstrings must be meaningful.

Ref: .intent/charter/standards/code_standards.json
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.models import AuditFinding, AuditSeverity


CODE_STANDARDS_POLICY = Path(".intent/charter/standards/code_standards.json")

# Regex for word-boundary matching to avoid false positives (e.g. "outbdated")
# Matches: Start of string or whitespace + term + whitespace or end of string/punctuation
PLACEHOLDER_PATTERNS = [
    re.compile(r"\bTBD\b", re.IGNORECASE),
    re.compile(r"\bN/A\b", re.IGNORECASE),
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"\bAUTO-ADDED\b", re.IGNORECASE),
    re.compile(r"\bPLACEHOLDER\b", re.IGNORECASE),
]


# ID: manifest-lint-enforcement
# ID: 07d4ee8d-7721-4159-bfb1-9d0ec784e9c4
class ManifestLintEnforcement(EnforcementMethod):
    """
    Checks for placeholder text in capability descriptions (docstrings).
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 6b812007-6f2b-478f-ad3a-97f14c20c465
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        """Finds capabilities with placeholder descriptions."""
        findings = []

        for symbol in context.symbols_list:
            # Skip private helpers (they don't need formal descriptions per policy)
            # Ref: symbols.private_helpers_no_id_required
            if symbol.get("name", "").startswith("_"):
                continue

            # "intent" in knowledge graph maps to the docstring/description
            description = (symbol.get("intent", "") or "").strip()

            # 1. Check for Empty Description (Meaningful Description Rule)
            if not description:
                # Only strictly enforce this on symbols that HAVE a capability ID
                if symbol.get("capability_id"):
                    findings.append(
                        AuditFinding(
                            check_id="caps.meaningful_description",
                            severity=self.severity,
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
                        self._create_finding(
                            message=(
                                f"Capability '{symbol.get('name')}' contains forbidden placeholder text: "
                                f"'{pattern.pattern}'"
                            ),
                            file_path=symbol.get("file_path"),
                            line_number=symbol.get("line_number"),
                        )
                    )
                    break  # One violation is enough

        return findings


# ID: ee190b8d-1bf0-4b1a-90e2-abf21ca013c9
class ManifestLintCheck(RuleEnforcementCheck):
    """
    Checks for placeholder text in capability descriptions (docstrings).

    Ref: .intent/charter/standards/code_standards.json
    """

    policy_rule_ids: ClassVar[list[str]] = [
        "caps.no_placeholder_text",
    ]

    policy_file: ClassVar[Path] = CODE_STANDARDS_POLICY

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        ManifestLintEnforcement(rule_id="caps.no_placeholder_text"),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
