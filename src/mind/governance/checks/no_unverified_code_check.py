# src/mind/governance/checks/no_unverified_code_check.py
"""
Enforces agent.execution.no_unverified_code: Dangerous primitives require defense-in-depth.

CONSTITUTIONAL: Trust zones and dangerous primitives are loaded from policy, not hardcoded.

Ref: .intent/charter/standards/operations/code_execution.json
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

CODE_EXECUTION_POLICY = Path(".intent/charter/standards/operations/code_execution.json")


# ID: no-unverified-code-enforcement
# ID: 57a7095c-63b7-4d35-88bf-3d170ac705a4
class NoUnverifiedCodeEnforcement(EnforcementMethod):
    """
    Scans for dangerous code execution primitives.
    Enforces multi-layer protection: Domain + Validation + Sandboxing + Docs.

    CONSTITUTIONAL PRINCIPLE: Trust zones loaded from policy, not hardcoded.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 7ccccb93-a63f-4855-adce-2eabea195ffc
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        # Load trust zones and dangerous primitives from policy (SSOT)
        code_exec_policy = context.policies.get("code_execution", {})

        # Extract allowed domains from trust_zones (system + privileged)
        trust_zones = code_exec_policy.get("trust_zones", {})
        allowed_domains = []
        for zone_name in ["system", "privileged"]:
            zone = trust_zones.get(zone_name, {})
            allowed_domains.extend(zone.get("domains", []))

        if not allowed_domains:
            logger.warning(
                "NoUnverifiedCodeCheck: No trust zones found in code_execution policy. "
                "Dangerous primitives will be flagged everywhere!"
            )

        # Get dangerous primitives from policy
        dangerous_primitives = set(code_exec_policy.get("dangerous_primitives", []))
        if not dangerous_primitives:
            logger.warning(
                "NoUnverifiedCodeCheck: No dangerous primitives defined in policy. "
                "Using default set."
            )
            dangerous_primitives = {"eval", "exec", "compile", "__import__"}

        # Convert domain names to file paths (e.g., "mind.governance" -> "src/mind/governance")
        trusted_paths = []
        for domain in allowed_domains:
            # Convert module notation to path
            path = domain.replace(".", "/")
            if not path.startswith("src/"):
                path = f"src/{path}"
            trusted_paths.append(path)

        logger.debug(
            "Trusted domains for dangerous primitives: %s", ", ".join(trusted_paths)
        )

        # Scan files efficiently
        for file_path in context.src_dir.rglob("*.py"):
            try:
                findings.extend(
                    self._check_file(
                        context, file_path, trusted_paths, dangerous_primitives
                    )
                )
            except Exception as e:
                logger.debug("Failed to check %s for dangerous code: %s", file_path, e)

        return findings

    def _check_file(
        self,
        context: AuditorContext,
        file_path: Path,
        trusted_paths: list[str],
        dangerous_primitives: set[str],
    ) -> list[AuditFinding]:
        findings = []
        rel_path = str(file_path.relative_to(context.repo_path)).replace("\\", "/")

        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError):
            return []

        # Find dangerous calls
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = self._get_func_name(node)

                if func_name in dangerous_primitives:
                    # Layer 1: Trust Zone (loaded from policy)
                    if not self._is_trusted_domain(rel_path, trusted_paths):
                        findings.append(
                            self._create_finding(
                                message=f"Dangerous primitive '{func_name}' is FORBIDDEN in this domain. Allowed domains: {', '.join(trusted_paths)}",
                                file_path=rel_path,
                                line_number=node.lineno,
                            )
                        )
                        continue

                    # Layer 2-4: Defense in Depth Analysis
                    if not self._verify_defense_in_depth(node, content, func_name):
                        findings.append(
                            self._create_finding(
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

    def _is_trusted_domain(self, file_path: str, trusted_paths: list[str]) -> bool:
        """Check if file is in a trusted domain (loaded from policy)."""
        return any(file_path.startswith(domain) for domain in trusted_paths)

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
            if node.args and isinstance(node.args[0], ast.Constant):
                return True

        return has_validation and has_sandbox and has_docs


# ID: e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8a9b
class NoUnverifiedCodeCheck(RuleEnforcementCheck):
    """
    Scans for dangerous code execution primitives.
    Enforces multi-layer protection: Domain + Validation + Sandboxing + Docs.

    CONSTITUTIONAL: Trust zones and dangerous primitives loaded from policy.

    Ref: .intent/charter/standards/operations/code_execution.json
    """

    policy_rule_ids: ClassVar[list[str]] = ["agent.execution.no_unverified_code"]

    policy_file: ClassVar[Path] = CODE_EXECUTION_POLICY

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        NoUnverifiedCodeEnforcement(rule_id="agent.execution.no_unverified_code"),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
