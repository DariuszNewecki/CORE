# src/mind/governance/checks/cli_naming_check.py
"""
Enforces symbols.cli_async_helpers_private: Async CLI helpers must be private.

CONSTITUTIONAL COMPLIANCE:
- Uses knowledge_graph from AuditorContext (DB SSOT)
- Distinguishes between entry points and helpers based on capability assignment and call graph
"""

from __future__ import annotations

from mind.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: 58eda072-18cf-4fc5-ac41-8a122d62a434
class CliNamingCheck(BaseCheck):
    """
    Scans CLI logic modules to ensure async helper functions are private (start with '_').

    CORRECTED: Now uses knowledge graph (DB SSOT) instead of filesystem scanning.
    Distinguishes between entry points (can be public) and helpers (must be private).
    """

    policy_rule_ids = ["symbols.cli_async_helpers_private"]

    # ID: 0a6fd53b-fbc4-4147-a847-e03e5c71ca8f
    def execute(self) -> list[AuditFinding]:
        findings = []

        # SSOT: Query knowledge graph from database, not filesystem
        symbols = self.context.knowledge_graph.get("symbols", {})

        for symbol_key, symbol_data in symbols.items():
            # Only check async functions in cli/logic namespace
            if not self._is_cli_logic_async_function(symbol_data):
                continue

            function_name = symbol_data.get("name", "")

            # Skip if already private (starts with '_')
            if function_name.startswith("_"):
                continue

            # Determine if this is an entry point or a helper
            if self._is_entry_point(symbol_data, symbols):
                continue  # Entry points can be public

            # This is a helper - must be private
            findings.append(
                AuditFinding(
                    check_id="symbols.cli_async_helpers_private",
                    severity=AuditSeverity.ERROR,
                    message=(
                        f"Public async function '{function_name}' found in CLI logic. "
                        f"Async CLI helpers must be private (prefix with '_'). "
                        f"Entry points should have capabilities assigned or be called by commands."
                    ),
                    file_path=symbol_data.get("file_path", ""),
                    line_number=symbol_data.get("line_number", 0),
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
        return "src/body/cli/logic/" in file_path

    def _is_entry_point(self, symbol_data: dict, all_symbols: dict) -> bool:
        """
        Determine if a function is an entry point rather than a helper.

        Entry points are identified by:
        1. Having a capability assignment (registered in manifest)
        2. Being called by other functions (has inbound references)
        3. Having decorators that indicate registration (@command, etc.)
        """
        # Check 1: Has capability assignment
        if symbol_data.get("capability"):
            return True

        # Check 2: Has callers (referenced by other symbols)
        symbol_key = symbol_data.get("qualified_name", "")
        for other_symbol in all_symbols.values():
            calls = other_symbol.get("calls", [])
            if symbol_key in calls:
                return True

        # Check 3: Has registration decorators (future enhancement)
        # Could check symbol_data.get("decorators", []) for @command, @register_command, etc.

        return False
