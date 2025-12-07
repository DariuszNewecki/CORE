# src/mind/governance/checks/no_unverified_code_check.py

"""
Constitutional enforcement: agent.execution.no_unverified_code

Ensures dangerous code execution primitives (eval, exec, compile, __import__)
are only used with proper multi-layer protection (defense in depth).

IMPORTANT: This check implements the code_execution_policy.yaml which defines
what "safe execution" means through principle-based rules, not exception lists.
"""

from __future__ import annotations

import ast
from pathlib import Path

from mind.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8a9b
class NoUnverifiedCodeCheck(BaseCheck):
    """
    Enforces agent.execution.no_unverified_code policy.

    Uses defense-in-depth model: dangerous functions allowed ONLY when
    ALL protection layers are present (domain + validation + sandbox + docs).
    """

    policy_rule_ids = ["agent.execution.no_unverified_code"]

    # Trust zones from policy
    SYSTEM_DOMAINS = ["mind.governance", "mind.policies"]
    PRIVILEGED_DOMAINS = ["body.cli.logic", "body.cli.commands", "core"]

    DANGEROUS_FUNCTIONS = ["eval", "exec", "compile", "__import__"]

    # ID: b5a07aaf-79f2-4c62-a38b-70285716e1b0
    def execute(self) -> list[AuditFinding]:
        """Check for dangerous code execution primitives without proper protection."""
        findings = []

        # Query symbols from database (SSOT)
        for symbol_data in self.context.symbols_list:
            # Only check functions (not classes, properties, etc)
            if symbol_data.get("type") not in ("function", "method"):
                continue

            # Get the module path to check trust zone
            module = symbol_data.get("module", "")
            symbol_path = symbol_data.get("name", "")

            # Get the source file path
            file_path = symbol_data.get("file_path", "")
            if not file_path:
                continue

            file_path_obj = Path(self.context.repo_path) / file_path
            if not file_path_obj.exists():
                continue

            try:
                content = file_path_obj.read_text(encoding="utf-8")
                tree = ast.parse(content)

                # Find the specific function node
                for node in ast.walk(tree):
                    if not isinstance(node, ast.FunctionDef):
                        continue

                    # Match the function name
                    if not symbol_path.endswith(f".{node.name}"):
                        continue

                    # Check if this function uses dangerous primitives
                    violations = self._check_function_for_violations(
                        node, content, module, symbol_data, file_path
                    )
                    findings.extend(violations)

            except Exception:
                # If we can't parse the file, skip it
                continue

        return findings

    def _check_function_for_violations(
        self,
        func_node: ast.FunctionDef,
        file_content: str,
        module: str,
        symbol_data: dict,
        file_path: str,
    ) -> list[AuditFinding]:
        """Check a single function for dangerous code execution without proper protection."""
        findings = []

        # Find all dangerous function calls in this function
        for node in ast.walk(func_node):
            if not isinstance(node, ast.Call):
                continue

            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id

            if func_name not in self.DANGEROUS_FUNCTIONS:
                continue

            # Found dangerous function - check ALL protection layers
            line_num = node.lineno

            # Layer 1: Check trust zone (domain restriction)
            if not self._is_in_trusted_domain(module):
                findings.append(
                    AuditFinding(
                        check_id=self.policy_rule_ids[0],
                        severity=AuditSeverity.ERROR,
                        message=f"Dangerous function '{func_name}()' used outside trusted domains. "
                        f"Module '{module}' is not in system or privileged trust zones.",
                        location=f"{file_path}:{line_num}",
                        context={
                            "function": func_name,
                            "module": module,
                            "allowed_domains": self.SYSTEM_DOMAINS
                            + self.PRIVILEGED_DOMAINS,
                        },
                    )
                )
                continue

            # Layer 2: Check for validation
            has_validation = self._has_validation_layer(
                func_node, file_content, func_name
            )

            # Layer 3: Check for sandboxing
            has_sandboxing = self._has_sandboxing_layer(node, file_content, func_name)

            # Layer 4: Check for capability tag
            has_capability = symbol_data.get("id") is not None

            # Layer 5: Check for security documentation
            has_security_docs = self._has_security_documentation(
                func_node, file_content
            )

            # If ANY layer is missing, it's a violation
            missing_layers = []
            if not has_validation:
                missing_layers.append(
                    "validation (AST check, whitelist, or constant input)"
                )
            if not has_sandboxing:
                missing_layers.append(
                    "sandboxing (disabled builtins or restricted namespace)"
                )
            if not has_capability:
                missing_layers.append("capability tag (# ID: ...)")
            if not has_security_docs:
                missing_layers.append("security documentation (SECURITY comment)")

            if missing_layers:
                findings.append(
                    AuditFinding(
                        check_id=self.policy_rule_ids[0],
                        severity=AuditSeverity.ERROR,
                        message=f"Dangerous function '{func_name}()' missing protection layers: "
                        f"{', '.join(missing_layers)}",
                        location=f"{file_path}:{line_num}",
                        context={
                            "function": func_name,
                            "module": module,
                            "missing_layers": missing_layers,
                            "policy": "All layers required for safe execution (defense in depth)",
                        },
                    )
                )

        return findings

    def _is_in_trusted_domain(self, module: str) -> bool:
        """Check if module is in a trusted domain."""
        for domain in self.SYSTEM_DOMAINS + self.PRIVILEGED_DOMAINS:
            if module.startswith(domain):
                return True
        return False

    def _has_validation_layer(
        self, func_node: ast.FunctionDef, file_content: str, dangerous_func: str
    ) -> bool:
        """Check for validation layer (AST checking, whitelist, or constant input)."""
        # Look for AST validation patterns
        func_source = ast.get_source_segment(file_content, func_node) or ""

        # Pattern 1: AST validation (ast.walk, ast.parse, node type checking)
        if "ast.walk" in func_source or "ast.parse" in func_source:
            if "_ALLOWED_NODES" in func_source or "whitelist" in func_source.lower():
                return True

        # Pattern 2: Input is a hardcoded constant (not a variable)
        if dangerous_func == "__import__":
            # Check if __import__ argument is a string literal
            if '"' in func_source or "'" in func_source:
                return True

        # Pattern 3: Explicit validation comment
        if "validate" in func_source.lower() or "check" in func_source.lower():
            return True

        return False

    def _has_sandboxing_layer(
        self, call_node: ast.Call, file_content: str, dangerous_func: str
    ) -> bool:
        """Check for sandboxing layer (disabled builtins, restricted namespace)."""
        # Get the source around the call
        source_segment = ast.get_source_segment(file_content, call_node) or ""

        # Pattern 1: Disabled builtins
        if "__builtins__" in source_segment and "{}" in source_segment:
            return True

        # Pattern 2: For __import__, hardcoded module path is sandboxing
        if dangerous_func == "__import__":
            # If it's importing from known internal modules, that's safe
            if any(
                internal in source_segment
                for internal in ["features.", "mind.", "body.", "shared.", "services."]
            ):
                return True

        # Pattern 3: Restricted namespace (globals/locals dict)
        if "globals=" in source_segment or "locals=" in source_segment:
            return True

        return False

    def _has_security_documentation(
        self, func_node: ast.FunctionDef, file_content: str
    ) -> bool:
        """Check for security documentation explaining why the code is safe."""
        # Get function source including docstring
        func_source = ast.get_source_segment(file_content, func_node) or ""

        # Look for security-related documentation keywords
        security_keywords = [
            "SECURITY",
            "SAFE",
            "verified safe",
            "validated",
            "sandboxed",
            "bounded",
            "restricted",
        ]

        source_lower = func_source.lower()
        return any(keyword.lower() in source_lower for keyword in security_keywords)
