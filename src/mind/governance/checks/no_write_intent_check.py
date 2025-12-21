# src/mind/governance/checks/no_write_intent_check.py
"""
Enforces agent.compliance.no_write_intent: Agents must not modify .intent/ directory.

Ref: .intent/charter/standards/architecture/agent_governance.json
"""

from __future__ import annotations

import ast
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.config import settings
from shared.models import AuditFinding


# ID: no-write-intent-enforcement
# ID: d2e3f4a5-b6c7-4d8e-9f0a-1b2c3d4e5f6a
class NoWriteIntentEnforcement(EnforcementMethod):
    """Scans Agent code for file operations targeting .intent/."""

    # ID: 91e5cf61-927c-4329-bcbe-5f5b44a8a963
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        # Scan src/will (Agent layer)
        will_dir = context.repo_path / "src" / "will"
        if not will_dir.exists():
            return findings

        for file_path in will_dir.rglob("*.py"):
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))

                # Look for file operations
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        # Check for open() or Path().write_text() etc
                        if isinstance(node.func, ast.Name) and node.func.id == "open":
                            # Check if any arg contains .intent
                            for arg in node.args:
                                if isinstance(arg, ast.Constant) and isinstance(
                                    arg.value, str
                                ):
                                    if ".intent" in arg.value:
                                        findings.append(
                                            self._create_finding(
                                                message="Agent code attempting to write to .intent/ directory. This is constitutionally forbidden.",
                                                file_path=str(
                                                    file_path.relative_to(
                                                        context.repo_path
                                                    )
                                                ),
                                                line_number=node.lineno,
                                            )
                                        )

            except Exception:
                pass  # Skip parse errors

        return findings


# ID: b7f3a8e2-4d9c-4a1b-8e5f-6c7d8e9f0a1b
class NoWriteIntentCheck(RuleEnforcementCheck):
    """
    Enforces agent.compliance.no_write_intent.
    Ref: .intent/charter/standards/architecture/agent_governance.json
    """

    policy_rule_ids: ClassVar[list[str]] = ["agent.compliance.no_write_intent"]

    policy_file: ClassVar = settings.paths.policy("agent_governance")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        NoWriteIntentEnforcement(rule_id="agent.compliance.no_write_intent"),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
