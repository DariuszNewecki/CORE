# src/mind/governance/checks/no_write_intent_check.py
"""
Enforces agent.compliance.no_write_intent and Layer Separation.
Agents (Will Layer) must NOT perform direct file I/O.
They must delegate side effects to the Body layer (Atomic Actions).
"""

from __future__ import annotations

import ast

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

# Heuristic list of forbidden write methods in the Agent layer
FORBIDDEN_METHODS = {"write_text", "write_bytes", "mkdir", "rmdir", "unlink", "rename"}
FORBIDDEN_FUNCTIONS = {"open", "remove", "rmtree"}


# ID: b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e
class NoWriteIntentCheck(BaseCheck):
    """
    Scans the Will Layer (src/will) for direct file I/O operations.
    Agents must produce Decisions/Plans, not side effects.
    Ref: standard_architecture_agent_governance
    """

    policy_rule_ids = ["agent.compliance.no_write_intent"]

    # ID: 83b325f8-2a02-41ea-85ab-12f9c34b2c73
    def execute(self) -> list[AuditFinding]:
        findings = []

        # 1. Scope: Only scan the Will Layer (Agents)
        # Writing in src/body or src/services is ALLOWED (that's their job).
        agent_dir = self.src_dir / "will"
        if not agent_dir.exists():
            return findings

        for file_path in agent_dir.rglob("*.py"):
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))

                rel_path = str(file_path.relative_to(self.repo_root))

                for node in ast.walk(tree):
                    # Check 1: Forbidden Method Calls (e.g., path.write_text())
                    if isinstance(node, ast.Call) and isinstance(
                        node.func, ast.Attribute
                    ):
                        if node.func.attr in FORBIDDEN_METHODS:
                            findings.append(
                                self._create_finding(
                                    rel_path,
                                    node.lineno,
                                    f"Method '{node.func.attr}()'",
                                )
                            )

                    # Check 2: Forbidden Function Calls (e.g., open())
                    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        if node.func.id in FORBIDDEN_FUNCTIONS:
                            # Refine 'open' check: only if mode is 'w', 'a', 'x', 'r+'
                            if node.func.id == "open":
                                if not self._is_write_mode(node):
                                    continue  # Read-only open is suspicious but arguably okay?
                                    # Strictly, Agents shouldn't read directly either (ContextBuilder),
                                    # but writes are the constitutional violation here.

                            findings.append(
                                self._create_finding(
                                    rel_path,
                                    node.lineno,
                                    f"Function '{node.func.id}()'",
                                )
                            )

            except Exception as e:
                logger.debug("Failed to scan %s for write intent: %s", file_path, e)

        return findings

    def _is_write_mode(self, node: ast.Call) -> bool:
        """Heuristic to check if open() is called with write mode."""
        # 1. Check positional args: open(file, 'w')
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
            return any(m in str(node.args[1].value) for m in ("w", "a", "x", "+"))

        # 2. Check keyword args: open(file, mode='w')
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                return any(m in str(kw.value.value) for m in ("w", "a", "x", "+"))

        return False  # Default is read 'r'

    def _create_finding(self, file_path: str, line: int, trigger: str) -> AuditFinding:
        return AuditFinding(
            check_id="agent.compliance.no_write_intent",
            severity=AuditSeverity.ERROR,
            message=(
                f"Direct I/O detected ({trigger}) in Agent layer. "
                "Agents must not write to disk directly; delegate to Body layer (Atomic Actions)."
            ),
            file_path=file_path,
            line_number=line,
        )
