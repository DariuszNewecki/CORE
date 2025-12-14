# src/mind/governance/checks/no_unverified_code_check.py
"""
Enforces agent.execution.no_unverified_code: Dangerous primitives require defense-in-depth.
Ref: standard_operations_code_execution
"""

from __future__ import annotations

import ast
from pathlib import Path

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

DANGEROUS_FUNCTIONS = {"eval", "exec", "compile", "__import__"}

# Trust Zones defined in standard_operations_code_execution
TRUSTED_DOMAINS = [
    "src/mind/governance",
    "src/mind/policies",
    "src/body/cli/logic",
    "src/body/cli/commands",
    "src/core",
]


# ID: e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8a9b
class NoUnverifiedCodeCheck(BaseCheck):
    """
    Scans for dangerous code execution primitives.
    Enforces multi-layer protection: Domain + Validation + Sandboxing + Docs.
    """

    policy_rule_ids = ["agent.execution.no_unverified_code"]

    # ID: b5a07aaf-79f2-4c62-a38b-70285716e1b0
    def execute(self) -> list[AuditFinding]:
        findings = []

        # Scan files efficiently
        for file_path in self.src_dir.rglob("*.py"):
            try:
                findings.extend(self._check_file(file_path))
            except Exception as e:
                logger.debug("Failed to check %s for dangerous code: %s", file_path, e)

        return findings

    def _check_file(self, file_path: Path) -> list[AuditFinding]:
        findings = []
        rel_path = str(file_path.relative_to(self.repo_root)).replace("\\", "/")

        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError):
            return []

        # Find dangerous calls
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = self._get_func_name(node)

                if func_name in DANGEROUS_FUNCTIONS:
                    # Layer 1: Trust Zone
                    if not self._is_trusted_domain(rel_path):
                        findings.append(
                            AuditFinding(
                                check_id="agent.execution.no_unverified_code",
                                severity=AuditSeverity.ERROR,
                                message=f"Dangerous primitive '{func_name}' is FORBIDDEN in this domain.",
                                file_path=rel_path,
                                line_number=node.lineno,
                                context={
                                    "domain": rel_path,
                                    "allowed": TRUSTED_DOMAINS,
                                },
                            )
                        )
                        continue

                    # Layer 2-4: Defense in Depth Analysis
                    # We need the parent function context to check for validation/docs
                    # Simple heuristic: Check if file contains security markers near the usage
                    # Real implementation would require parent pointer in AST traversal

                    if not self._verify_defense_in_depth(node, content, func_name):
                        findings.append(
                            AuditFinding(
                                check_id="agent.execution.no_unverified_code",
                                severity=AuditSeverity.ERROR,
                                message=(
                                    f"Dangerous primitive '{func_name}' missing required protections. "
                                    "Must have: Validation + Sandboxing + Security Docs."
                                ),
                                file_path=rel_path,
                                line_number=node.lineno,
                            )
                        )

        return findings

    def _get_func_name(self, call_node: ast.Call) -> str | None:
        if isinstance(call_node.func, ast.Name):
            return call_node.func.id
        return None

    def _is_trusted_domain(self, file_path: str) -> bool:
        return any(file_path.startswith(domain) for domain in TRUSTED_DOMAINS)

    def _verify_defense_in_depth(
        self, node: ast.Call, content: str, func_name: str
    ) -> bool:
        """
        Heuristic check for defense layers.
        In a real AST walk we'd check the parent function node.
        Here we scan the surrounding lines for evidence.
        """
        # Get context window (10 lines before/after)
        lines = content.splitlines()
        start = max(0, node.lineno - 10)
        end = min(len(lines), node.lineno + 5)
        context_block = "\n".join(lines[start:end])

        # Check Validation (Layer 2)
        has_validation = (
            "ast.walk" in context_block
            or "validate" in context_block.lower()
            or "whitelist" in context_block.lower()
        )

        # Check Sandboxing (Layer 3)
        has_sandbox = "__builtins__" in context_block or "globals=" in context_block

        # Check Documentation (Layer 4)
        has_docs = "SECURITY" in context_block or "SAFE" in context_block

        # Exceptions for __import__ if literal string
        if func_name == "__import__":
            # If literal string, it's safer
            # Simple check: is the arg a constant?
            if node.args and isinstance(node.args[0], ast.Constant):
                return True

        return has_validation and has_sandbox and has_docs
