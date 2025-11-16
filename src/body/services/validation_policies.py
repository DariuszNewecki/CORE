# src/body/services/validation_policies.py
"""
Policy-aware validation logic for enforcing safety and security policies.
This module is given pre-loaded policies and scans AST nodes for violations.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

Violation = dict[str, Any]


# ID: dcff1afd-963d-419c-8f66-31978115cfc9
class PolicyValidator:
    """Handles policy-aware validation including safety checks and forbidden patterns."""

    def __init__(self, safety_policy_rules: list[dict]):
        """
        Initialize the policy validator with pre-loaded safety policy rules.
        """
        self.safety_rules = safety_policy_rules

    def _get_full_attribute_name(self, node: ast.Attribute) -> str:
        """Recursively builds the full name of an attribute call."""
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.insert(0, current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.insert(0, current.id)
        return ".".join(parts)

    def _find_dangerous_patterns(
        self, tree: ast.AST, file_path: str
    ) -> list[Violation]:
        """Scans the AST for calls and imports forbidden by safety policies."""
        violations: list[Violation] = []
        rules = self.safety_rules

        forbidden_calls = set()
        forbidden_imports = set()

        for rule in rules:
            exclude_patterns = [
                p
                for p in rule.get("scope", {}).get("exclude", [])
                if isinstance(p, str)
            ]
            is_excluded = any(Path(file_path).match(p) for p in exclude_patterns)

            if is_excluded:
                continue

            if rule.get("id") == "no_dangerous_execution":
                patterns = {
                    p.replace("(", "")
                    for p in rule.get("detection", {}).get("patterns", [])
                }
                forbidden_calls.update(patterns)
            elif rule.get("id") == "no_unsafe_imports":
                patterns = {
                    imp.split(" ")[-1]
                    for imp in rule.get("detection", {}).get("forbidden", [])
                }
                forbidden_imports.update(patterns)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                full_call_name = ""
                if isinstance(node.func, ast.Name):
                    full_call_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    full_call_name = self._get_full_attribute_name(node.func)

                if full_call_name in forbidden_calls:
                    violations.append(
                        {
                            "rule": "safety.dangerous_call",
                            "message": f"Use of forbidden call: '{full_call_name}'",
                            "line": node.lineno,
                            "severity": "error",
                        }
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in forbidden_imports:
                        violations.append(
                            {
                                "rule": "safety.forbidden_import",
                                "message": f"Import of forbidden module: '{alias.name}'",
                                "line": node.lineno,
                                "severity": "error",
                            }
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in forbidden_imports:
                    violations.append(
                        {
                            "rule": "safety.forbidden_import",
                            "message": f"Import from forbidden module: '{node.module}'",
                            "line": node.lineno,
                            "severity": "error",
                        }
                    )
        return violations

    # ID: d6059c1e-83ab-4c9a-8ebf-e596fa79494d
    def check_semantics(self, code: str, file_path: str) -> list[Violation]:
        """Runs all policy-aware semantic checks on a string of Python code."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []
        return self._find_dangerous_patterns(tree, file_path)
