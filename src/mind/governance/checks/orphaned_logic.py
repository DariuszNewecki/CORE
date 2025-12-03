# src/mind/governance/checks/orphaned_logic.py
"""
Constitutional enforcement: intent_alignment.

Ensures that all public symbols are assigned to a capability, enforcing
the 'intent_alignment' rule by preventing undocumented functionality.

CORRECTED VERSION: Properly handles classes, properties, framework entry points,
and distinguishes between callable functions and infrastructure code.
"""

from __future__ import annotations

import re
from typing import Any

from shared.models import AuditFinding, AuditSeverity

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.base_check import BaseCheck


# ID: 83663760-524c-4698-b77c-05a8883d9067
class OrphanedLogicCheck(BaseCheck):
    """
    Ensures that all public symbols are assigned to a capability, enforcing
    the 'intent_alignment' rule by preventing undocumented functionality.
    A symbol is considered an orphan if it is public, un-keyed, not a designated
    entry point, AND has no incoming calls from any other symbol.

    CORRECTED: Now properly handles:
    - Classes (used by instantiation, not calling)
    - Properties (not callable functions)
    - Framework entry points (FastAPI, decorators)
    - Base/abstract classes
    - Exception classes
    - Database models
    """

    policy_rule_ids = ["intent_alignment"]

    def __init__(self, context: AuditorContext):
        super().__init__(context)
        # The symbols_list is pre-loaded by the AuditorContext from the knowledge_graph VIEW
        self.all_symbols = self.context.symbols_list
        # Load entry point patterns directly from source_structure (they're embedded in project_structure.yaml)
        self.entry_point_patterns = self.context.source_structure.get(
            "entry_point_patterns", []
        )

    def _is_infrastructure_symbol(self, symbol_data: dict[str, Any]) -> bool:
        """
        Check if a symbol is infrastructure code that doesn't need explicit calling.

        Infrastructure includes:
        - Classes (used by instantiation)
        - Properties (accessed as attributes)
        - Database models
        - Exception classes
        - Base/abstract classes
        - Type definitions
        - Protocols/Interfaces
        """
        symbol_type = symbol_data.get("type", "")
        symbol_name = symbol_data.get("name", "")

        # All classes are infrastructure (instantiated, not called)
        if symbol_type == "class":
            return True

        # Properties are accessed as attributes, not called
        if symbol_type == "property":
            return True

        # Check for common infrastructure patterns in name
        infrastructure_patterns = [
            r"(Model|Schema|Config|Settings|Protocol)$",  # Data structures
            r"(Error|Exception|Warning)$",  # Exception classes
            r"Base[A-Z]",  # Base classes
            r"^[A-Z][a-z]+[A-Z]",  # CamelCase classes
        ]

        for pattern in infrastructure_patterns:
            if re.search(pattern, symbol_name):
                return True

        return False

    def _is_framework_entry_point(self, symbol_data: dict[str, Any]) -> bool:
        """
        Check if a symbol is a framework entry point.

        Framework entry points include:
        - FastAPI app factories (create_app, get_app)
        - FastAPI lifespan managers
        - FastAPI/Flask route handlers
        - Main entry points (if __name__ == "__main__")
        - Decorator implementations (wrapper functions)
        """
        symbol_name = symbol_data.get("name", "")
        file_path = symbol_data.get("file_path", "")

        # FastAPI patterns
        fastapi_patterns = [
            r"^(create_app|get_app|app_factory)$",
            r"^lifespan$",
            r"^health_check$",  # Health endpoints
        ]

        for pattern in fastapi_patterns:
            if re.search(pattern, symbol_name):
                return True

        # Main entry points
        if symbol_name == "main" and file_path.endswith(".py"):
            return True

        # Decorator wrapper functions (inner functions of decorators)
        if symbol_name in ("wrapper", "decorator", "inner"):
            return True

        return False

    def _is_special_method(self, symbol_data: dict[str, Any]) -> bool:
        """
        Check if symbol is a special method that's called implicitly.

        Special methods include:
        - Magic methods (__init__, __str__, etc.)
        - Property getters/setters
        - Context managers (__enter__, __exit__)
        - Decorators (@property, @staticmethod)
        """
        symbol_name = symbol_data.get("name", "")

        # Magic methods
        if re.match(r"^__.+__$", symbol_name):
            return True

        # Property-related
        if symbol_name in ("fget", "fset", "fdel"):
            return True

        return False

    def _is_only_functions(self, symbol_data: dict[str, Any]) -> bool:
        """
        Only check actual functions, not classes or properties.

        This is the critical fix: we were checking ALL symbols,
        but orphaned logic only applies to callable functions.
        """
        symbol_type = symbol_data.get("type", "")
        return symbol_type in ("function", "method")

    def _is_entry_point(self, symbol_data: dict[str, Any]) -> bool:
        """Checks if a symbol matches any of the defined entry point patterns."""
        # First check our new comprehensive patterns
        if self._is_infrastructure_symbol(symbol_data):
            return True

        if self._is_framework_entry_point(symbol_data):
            return True

        if self._is_special_method(symbol_data):
            return True

        # Then check configured patterns
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
            # CRITICAL FIX: Only check actual functions
            if not self._is_only_functions(symbol_data):
                continue

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
