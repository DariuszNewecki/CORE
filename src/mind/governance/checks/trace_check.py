# src/mind/governance/checks/trace_check.py
"""
Enforces agent.reasoning.trace_required: All reason() calls must be followed by TRACE logging.

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


# ID: trace-enforcement
# ID: 7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d
class TraceEnforcement(EnforcementMethod):
    """Verifies that reason() calls are followed by TRACE logging."""

    # ID: ac29a093-8fe2-4e6a-bdc6-2da895972079
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        for file_path in context.python_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))
                lines = content.splitlines()

                reason_calls = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id == "reason":
                            reason_calls.append(node.lineno)

                # Look for TRACE: in next 3 lines after reason()
                for lineno in reason_calls:
                    found_trace = False
                    for offset in range(1, 4):
                        check_line = lineno + offset - 1
                        if check_line < len(lines) and "TRACE:" in lines[check_line]:
                            found_trace = True
                            break
                    if not found_trace:
                        findings.append(
                            self._create_finding(
                                message="reason() called without TRACE: log. Add `logger.info('TRACE: ...')`.",
                                file_path=str(file_path.relative_to(context.repo_path)),
                                line_number=lineno,
                            )
                        )

            except Exception:
                findings.append(
                    self._create_finding(
                        message=f"Parse error in {file_path.name}",
                        file_path=str(file_path.relative_to(context.repo_path)),
                        line_number=1,
                    )
                )

        return findings


# ID: 599dcb6a-e809-498c-a319-67121529b34c
class ReasoningTraceCheck(RuleEnforcementCheck):
    """
    Enforces agent.reasoning.trace_required.
    Ref: .intent/charter/standards/architecture/agent_governance.json
    """

    policy_rule_ids: ClassVar[list[str]] = ["agent.reasoning.trace_required"]

    policy_file: ClassVar = settings.paths.policy("agent_governance")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        TraceEnforcement(rule_id="agent.reasoning.trace_required"),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
