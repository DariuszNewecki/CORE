# src/mind/governance/checks/cli_naming_check.py
"""
Enforces symbols.cli_async_helpers_private.
Async orchestration helpers in CLI logic must be private and ungoverned.
"""

from __future__ import annotations

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 58eda072-18cf-4fc5-ac41-8a122d62a434
class CliNamingCheck(BaseCheck):
    """
    Enforces that async functions in src/body/cli/logic/:
    1. Must start with '_' (underscore).
    2. Must NOT have a Capability ID.

    Ref: standard_code_general (symbols.cli_async_helpers_private)
    """

    policy_rule_ids = ["symbols.cli_async_helpers_private"]

    # ID: 0a6fd53b-fbc4-4147-a847-e03e5c71ca8f
    def execute(self) -> list[AuditFinding]:
        findings = []
        symbols = self.context.knowledge_graph.get("symbols", {})

        for symbol_key, symbol_data in symbols.items():
            # 1. Filter Scope: Must be async function in body/cli/logic
            if not self._is_cli_logic_async_function(symbol_data):
                continue

            name = symbol_data.get("name", "")
            file_path = symbol_data.get("file_path", "")
            line = symbol_data.get("line_number", 0)

            # 2. Check Naming (Must start with '_')
            if not name.startswith("_"):
                findings.append(
                    AuditFinding(
                        check_id="symbols.cli_async_helpers_private",
                        severity=AuditSeverity.ERROR,
                        message=(
                            f"Public async function '{name}' in CLI logic. "
                            "Async orchestration helpers must be private (prefix with '_')."
                        ),
                        file_path=file_path,
                        line_number=line,
                    )
                )

            # 3. Check Capabilities (Must NOT have ID)
            # The rule states: "MUST NOT receive capability IDs"
            if symbol_data.get("capability"):
                findings.append(
                    AuditFinding(
                        check_id="symbols.cli_async_helpers_private",
                        severity=AuditSeverity.ERROR,
                        message=(
                            f"Async CLI helper '{name}' has a Capability ID. "
                            "Orchestration helpers must remain ungoverned implementation details."
                        ),
                        file_path=file_path,
                        line_number=line,
                    )
                )

        return findings

    def _is_cli_logic_async_function(self, symbol_data: dict) -> bool:
        """Check if symbol is an async function in src/body/cli/logic/."""
        if symbol_data.get("kind") != "function":
            return False

        if not symbol_data.get("is_async", False):
            return False

        file_path = symbol_data.get("file_path", "")
        # Strict scope enforcement based on Rule ID definition
        return "src/body/cli/logic/" in file_path
