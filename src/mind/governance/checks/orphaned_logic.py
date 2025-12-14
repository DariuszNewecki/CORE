# src/mind/governance/checks/orphaned_logic.py
"""
Enforces intent_alignment: All public symbols must be used or documented.
Detects "Orphaned Logic" - code that exists but has no purpose (no calls, no capability ID).
Respects layer_contracts.yaml for architectural exemptions.
"""

from __future__ import annotations

import re
from typing import Any

import yaml

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 83663760-524c-4698-b77c-05a8883d9067
class OrphanedLogicCheck(BaseCheck):
    """
    Identifies public code that is neither called nor constitutionally recognized.
    Enforces 'intent_alignment'.
    """

    policy_rule_ids = ["intent_alignment"]

    def __init__(self, context: AuditorContext):
        super().__init__(context)
        self.all_symbols = self.context.symbols_list
        self.layer_rules = self._load_layer_contracts()

    def _load_layer_contracts(self) -> list[dict]:
        """Loads symbol governance rules from layer_contracts.yaml."""
        contract_path = (
            self.context.intent_path
            / "charter/standards/architecture/layer_contracts.yaml"
        )
        if not contract_path.exists():
            logger.warning("layer_contracts.yaml not found. Using default enforcement.")
            return []

        try:
            data = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
            return data.get("symbol_governance_rules", [])
        except Exception as e:
            logger.error("Failed to load layer contracts: %s", e)
            return []

    def _is_exempt_by_contract(self, symbol_data: dict[str, Any]) -> bool:
        """
        Checks if symbol matches any exemption rule in layer_contracts.yaml.
        """
        for rule in self.layer_rules:
            if rule.get("enforcement") != "exemption":
                continue

            criteria = rule.get("match_criteria", {})
            if self._evaluate_match_rule(criteria, symbol_data):
                return True

        return False

    def _evaluate_match_rule(self, criteria: dict, data: dict) -> bool:
        """Evaluates match criteria against symbol data."""
        # 1. Module Path
        if "module_path_contains" in criteria:
            path_check = criteria["module_path_contains"]
            file_path = data.get("file_path", "")

            # Handle list or string
            if isinstance(path_check, list):
                if not any(p in file_path for p in path_check):
                    return False
            elif path_check not in file_path:
                return False

        # 2. Name Regex
        if "name_regex" in criteria:
            name = data.get("name", "")
            if not re.search(criteria["name_regex"], name):
                return False

        # 3. Public/Private
        if "is_public_function" in criteria:
            is_public = data.get("is_public", False)
            if is_public is not criteria["is_public_function"]:
                return False

        # 4. Type
        if "type" in criteria:
            kind = data.get("type", "")
            expected = criteria["type"]
            if expected == "function":
                if kind not in ("function", "method"):
                    return False
            elif kind != expected:
                return False

        return True

    # ID: d7ea188f-280a-4ac1-ac98-ca0403e33291
    def execute(self) -> list[AuditFinding]:
        findings = []

        if not self.all_symbols:
            return findings

        # 1. Build Call Graph Cache
        all_called_symbols = set()
        for symbol_data in self.all_symbols:
            called_list = symbol_data.get("calls") or []
            all_called_symbols.update(called_list)

        orphaned_symbols = []

        for symbol_data in self.all_symbols:
            # Only check actual functions/methods
            if symbol_data.get("type") not in ("function", "method"):
                continue

            # Only check public symbols
            if not symbol_data.get("is_public", False):
                continue

            # If it has a Capability ID, it is NOT an orphan (it has intent)
            if symbol_data.get("capability"):
                continue

            # Check Architectural Exemptions (The Constitutional Fix)
            if self._is_exempt_by_contract(symbol_data):
                continue

            # Check Usage (Is it called?)
            qualname = symbol_data.get("name", "")
            short_name = qualname.split(".")[-1]

            is_called = (qualname in all_called_symbols) or (
                short_name in all_called_symbols
            )

            if not is_called:
                findings.append(
                    AuditFinding(
                        check_id="intent_alignment",
                        severity=AuditSeverity.ERROR,
                        message=(
                            f"Orphaned Logic: Public symbol '{short_name}' is unused, "
                            "has no Capability ID, and is not architecturally exempt."
                        ),
                        file_path=symbol_data.get("file_path", ""),
                        line_number=symbol_data.get("line_number"),
                        context={
                            "symbol": qualname,
                            "fix": "Add # ID: <uuid> tag or make private (_prefix).",
                        },
                    )
                )

        return findings
