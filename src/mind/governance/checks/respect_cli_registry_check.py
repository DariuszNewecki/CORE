# src/mind/governance/checks/respect_cli_registry_check.py
"""
Enforces agent.compliance.respect_cli_registry: Agents must only invoke registered CLI commands.

Ref: .intent/charter/standards/architecture/agent_governance.json
"""

from __future__ import annotations

import ast
from typing import Any, ClassVar

from sqlalchemy import text

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.config import settings
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger
from shared.models import AuditFinding


logger = getLogger(__name__)


# ID: respect-cli-registry-enforcement
# ID: e3f4a5b6-c7d8-4e9f-0a1b-2c3d4e5f6a7b
class RespectCliRegistryEnforcement(EnforcementMethod):
    """Verifies that Agent code only invokes registered CLI commands."""

    async def _get_registered_commands(self) -> set[str]:
        """Fetches valid command IDs from the database (SSOT)."""
        async with get_session() as session:
            result = await session.execute(
                text("SELECT id FROM capabilities WHERE cli_command IS NOT NULL")
            )
            return {row[0] for row in result.fetchall()}

    # ID: 405e6834-95ec-4a73-9243-475fe897dfdb
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        # This check requires async DB access, so we'll do a synchronous wrapper
        import asyncio

        try:
            registered_commands = asyncio.run(self._get_registered_commands())
        except Exception as e:
            logger.warning("Failed to fetch registered commands: %s", e)
            return findings

        will_dir = context.repo_path / "src" / "will"
        if not will_dir.exists():
            return findings

        for file_path in will_dir.rglob("*.py"):
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))

                # Look for subprocess.run(['core-admin', ...])
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if (
                            isinstance(node.func, ast.Attribute)
                            and node.func.attr == "run"
                        ):
                            # Check if first arg is a list starting with 'core-admin'
                            if node.args and isinstance(node.args[0], ast.List):
                                elements = node.args[0].elts
                                if elements and isinstance(elements[0], ast.Constant):
                                    if elements[0].value == "core-admin":
                                        # Extract command
                                        if len(elements) > 1 and isinstance(
                                            elements[1], ast.Constant
                                        ):
                                            cmd = elements[1].value
                                            if cmd not in registered_commands:
                                                findings.append(
                                                    self._create_finding(
                                                        message=f"Agent invoking unregistered CLI command: {cmd}",
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


# ID: 3442d405-5bc4-4833-9a26-619165b2c202
class RespectCliRegistryCheck(RuleEnforcementCheck):
    """
    Enforces agent.compliance.respect_cli_registry.
    Ref: .intent/charter/standards/architecture/agent_governance.json
    """

    policy_rule_ids: ClassVar[list[str]] = ["agent.compliance.respect_cli_registry"]

    policy_file: ClassVar = settings.paths.policy("agent_governance")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        RespectCliRegistryEnforcement(rule_id="agent.compliance.respect_cli_registry"),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
