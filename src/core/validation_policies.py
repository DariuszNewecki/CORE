# src/core/validation_policies.py
"""
Policy-aware validation logic for enforcing safety and security policies from configuration files.

This module handles loading safety policies from YAML configuration and scanning
AST nodes for violations of those policies, including dangerous function calls
and forbidden imports.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.config_loader import load_config
from shared.path_utils import get_repo_root

Violation = Dict[str, Any]


# CAPABILITY: validation.policy.enforce
class PolicyValidator:
    """Handles policy-aware validation including safety checks and forbidden patterns."""

    # CAPABILITY: core.validation_policies.initialize
    def __init__(self) -> None:
        """Initialize the policy validator with cached policies."""
        self._safety_policies_cache: Optional[List[Dict]] = None

    # CAPABILITY: validation.policy.load_safety
    def _load_safety_policies(self) -> List[Dict]:
        """Loads and caches the safety policies from the .intent directory.

        Returns:
            List of safety policy dictionaries loaded from YAML configuration
        """
        if self._safety_policies_cache is None:
            repo_root = get_repo_root()
            policies_path = repo_root / ".intent" / "policies" / "safety_policies.yaml"
            # --- THIS IS THE FIX ---
            # The load_config function is now smarter and only needs the path.
            # We remove the second argument, "yaml".
            policy_data = load_config(policies_path)
            # --- END OF FIX ---
            self._safety_policies_cache = policy_data.get("rules", [])
        return self._safety_policies_cache

    # CAPABILITY: core.ast.attribute_name_builder
    def _get_full_attribute_name(self, node: ast.Attribute) -> str:
        """Recursively builds the full name of an attribute call.

        Args:
            node: AST Attribute node to process

        Returns:
            Full dotted name of the attribute (e.g., 'os.path.join')
        """
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.insert(0, current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.insert(0, current.id)
        return ".".join(parts)

    # CAPABILITY: audit.check.dangerous_patterns
    def _find_dangerous_patterns(
        self, tree: ast.AST, file_path: str
    ) -> List[Violation]:
        """Scans the AST for calls and imports forbidden by safety policies.

        Args:
            tree: Parsed AST to scan
            file_path: Path to the file being analyzed (for exclusion matching)

        Returns:
            List of violations found in the code
        """
        violations: List[Violation] = []
        rules = self._load_safety_policies()

        forbidden_calls = set()
        forbidden_imports = set()

        for rule in rules:
            # Check if file is excluded from this rule
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
            # Check for dangerous function calls
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
            # Check for forbidden imports
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

    # CAPABILITY: audit.check.semantics
    def check_semantics(self, code: str, file_path: str) -> List[Violation]:
        """Runs all policy-aware semantic checks on a string of Python code.

        Args:
            code: The Python source code to analyze
            file_path: Path to the file being analyzed

        Returns:
            List of policy violations found in the code
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            # Syntax errors are caught by check_syntax, so we can ignore them here.
            return []
        return self._find_dangerous_patterns(tree, file_path)
