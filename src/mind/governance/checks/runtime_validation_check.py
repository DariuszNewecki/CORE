# src/mind/governance/checks/runtime_validation_check.py
"""
Enforces agent.execution.require_runtime_validation.
Dangerous primitives (eval, exec) in Trusted Domains MUST have runtime input validation.
Ref: standard_operations_code_execution
"""

from __future__ import annotations

import ast
from pathlib import Path

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

# Dangerous primitives requiring runtime guards
DANGEROUS_FUNCTIONS = {"eval", "exec", "compile"}

# Trusted domains where these functions are allowed (if validated)
# Ref: standard_operations_code_execution -> trust_zones
CHECKED_DOMAINS = [
    "src/mind/governance",
    "src/mind/policies",
    "src/body/cli/logic",
    "src/body/cli/commands",
    "src/core",
]


# ID: 5f409021-f114-4db8-92c9-1b2f8372340f
class RuntimeValidationCheck(BaseCheck):
    """
    Scans Trusted Domains for usage of 'eval'/'exec'.
    Verifies that such usage is preceded by explicit runtime checks/assertions.
    """

    policy_rule_ids = ["agent.execution.require_runtime_validation"]

    # ID: 37a6aaf1-d9ca-4b8d-9fdf-fb107a679a21
    def execute(self) -> list[AuditFinding]:
        """Check that dangerous functions have runtime validation."""
        findings = []

        # Optimization: Filter file list first based on Trusted Domains
        # We don't need to check Untrusted domains here; NoUnverifiedCodeCheck bans them entirely.
        files_to_scan = []
        for domain in CHECKED_DOMAINS:
            domain_path = self.repo_root / domain
            if domain_path.exists():
                files_to_scan.extend(domain_path.rglob("*.py"))

        for file_path in set(files_to_scan):
            try:
                findings.extend(self._check_file(file_path))
            except Exception as e:
                logger.debug(
                    "Failed to check runtime validation in %s: %s", file_path, e
                )

        return findings

    def _check_file(self, file_path: Path) -> list[AuditFinding]:
        findings = []
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError):
            return []

        rel_path = str(file_path.relative_to(self.repo_root))

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = self._get_func_name(node)

                if func_name in DANGEROUS_FUNCTIONS:
                    # We found a dangerous call in a trusted domain.
                    # Now we must verify it has runtime validation.

                    if not self._has_runtime_validation(node, content):
                        findings.append(
                            AuditFinding(
                                check_id="agent.execution.require_runtime_validation",
                                severity=AuditSeverity.ERROR,
                                message=(
                                    f"Dangerous function '{func_name}()' missing runtime validation. "
                                    "Trusted Code MUST validate inputs before execution "
                                    "(e.g., 'if not safe: raise', 'assert', or 'Runtime validation:' comment)."
                                ),
                                file_path=rel_path,
                                line_number=node.lineno,
                                context={"function": func_name},
                            )
                        )
        return findings

    def _get_func_name(self, call_node: ast.Call) -> str | None:
        if isinstance(call_node.func, ast.Name):
            return call_node.func.id
        return None

    def _has_runtime_validation(self, call_node: ast.Call, file_content: str) -> bool:
        """
        Heuristic: Scans the lines preceding the call for validation patterns.
        """
        lines = file_content.splitlines()
        # Look back up to 15 lines
        start = max(0, call_node.lineno - 15)
        end = call_node.lineno - 1  # Stop before the call

        context_block = "\n".join(lines[start:end]).lower()

        # Validation Patterns
        validation_signals = [
            "runtime validation",
            "runtime check",
            "validate",
            "sanitize",
            "whitelist",
            "allowed_nodes",
            "ast.walk",  # Implies inspecting structure
            "isinstance",
            "if type(",
            "if not ",
            "assert ",
            "raise valueerror",
            "raise typeerror",
            "security check",
        ]

        return any(signal in context_block for signal in validation_signals)
