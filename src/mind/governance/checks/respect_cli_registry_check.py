# src/mind/governance/checks/respect_cli_registry_check.py
"""
Enforces agent.compliance.respect_cli_registry: Agents must only invoke registered CLI commands.

Ref: .intent/policies/architecture/agent_governance.json
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
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger
from shared.models import AuditFinding


logger = getLogger(__name__)


# ID: e3f4a5b6-c7d8-4e9f-0a1b-2c3d4e5f6a7b
class RespectCliRegistryEnforcement(EnforcementMethod):
    """Verifies that Agent code only invokes registered CLI commands."""

    async def _get_registered_commands(self) -> set[str]:
        """
        Fetches valid CLI command names from the database (SSOT).

        SSOT: core.cli_commands.name (e.g., "check.audit", "fix.code-style").
        """
        async with get_session() as session:
            result = await session.execute(text("SELECT name FROM core.cli_commands"))
            return {row[0] for row in result.fetchall()}

    @staticmethod
    def _extract_core_admin_command(node: ast.Call) -> str | None:
        """
        Extract canonical command name from a subprocess.run([...]) call.

        Supports:
          ["core-admin", "<group>", "<action>", ...]
          ["poetry", "run", "core-admin", "<group>", "<action>", ...]
        Ignores flags/options (tokens starting with '-').

        Returns:
          "<group>.<action>" when both exist, otherwise "<group>".
          None when no command tokens are present (e.g., "--help" only).
        """
        if not node.args or not isinstance(node.args[0], ast.List):
            return None

        elements = node.args[0].elts

        argv: list[str] = []
        for elt in elements:
            if not isinstance(elt, ast.Constant):
                return None
            if not isinstance(elt.value, str):
                return None
            argv.append(elt.value)

        try:
            i = argv.index("core-admin")
        except ValueError:
            return None

        tail = argv[i + 1 :]

        # Skip flags like --help, -v, etc.
        tail = [t for t in tail if not t.startswith("-")]

        if not tail:
            return None

        group = tail[0]
        action = tail[1] if len(tail) > 1 else None

        if action:
            return f"{group}.{action}"
        return group

    # ID: 405e6834-95ec-4a73-9243-475fe897dfdb
    async def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        try:
            registered_commands = await self._get_registered_commands()
        except Exception as e:
            logger.warning("Failed to fetch registered CLI commands: %s", e)
            return findings

        will_dir = context.repo_path / "src" / "will"
        if not will_dir.exists():
            return findings

        for file_path in will_dir.rglob("*.py"):
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))
            except Exception:
                continue  # Skip parse/read errors

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not (
                    isinstance(node.func, ast.Attribute) and node.func.attr == "run"
                ):
                    continue

                cmd = self._extract_core_admin_command(node)
                if not cmd:
                    continue

                if cmd not in registered_commands:
                    findings.append(
                        self._create_finding(
                            message=f"Agent invoking unregistered CLI command: {cmd}",
                            file_path=str(file_path.relative_to(context.repo_path)),
                            line_number=getattr(node, "lineno", 0),
                        )
                    )

        return findings


# ID: 3442d405-5bc4-4833-9a26-619165b2c202
class RespectCliRegistryCheck(RuleEnforcementCheck):
    """
    Enforces agent.compliance.respect_cli_registry.
    Ref: .intent/policies/architecture/agent_governance.json
    """

    policy_rule_ids: ClassVar[list[str]] = ["agent.compliance.respect_cli_registry"]

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        RespectCliRegistryEnforcement(rule_id="agent.compliance.respect_cli_registry"),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
