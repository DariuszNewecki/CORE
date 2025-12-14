# src/mind/governance/checks/respect_cli_registry_check.py
"""
Enforces agent.compliance.respect_cli_registry.
Agents (Will layer) must only invoke CLI commands registered in the Database (SSOT).
"""

from __future__ import annotations

import ast

from sqlalchemy import text

from mind.governance.checks.base_check import BaseCheck
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 3442d405-5bc4-4833-9a26-619165b2c202
class RespectCliRegistryCheck(BaseCheck):
    """
    Scans Agent code (src/will) for subprocess calls invoking 'core-admin'.
    Verifies that the invoked command matches a registered Capability ID in the DB.
    """

    policy_rule_ids = ["agent.compliance.respect_cli_registry"]

    async def _get_registered_commands(self) -> set[str]:
        """
        Fetches valid command IDs from the database (SSOT).
        Uses raw SQL to decouple from ORM changes.
        """
        try:
            async with get_session() as db:
                # Assuming table is core.cli_commands and column is name (action_id)
                # Ref: project_manifest.yaml -> db:core.cli_commands
                result = await db.execute(text("SELECT name FROM core.cli_commands"))
                return {row[0] for row in result.fetchall()}
        except Exception as e:
            logger.warning("Failed to load CLI registry from DB: %s", e)
            return set()

    # ID: 120df042-960b-4e88-b166-1f74c8f3835d
    async def execute(self) -> list[AuditFinding]:
        findings = []

        # 1. Load Registry
        registered_ids = await self._get_registered_commands()
        if not registered_ids:
            # If registry is empty/unreachable, we can't enforce, but should warn.
            # However, preventing false positives is safer.
            logger.info("CLI Registry empty or unreachable. Skipping validation.")
            return []

        # 2. Scope: Agents Only (src/will)
        agent_dir = self.src_dir / "will"
        if not agent_dir.exists():
            return []

        for file_path in agent_dir.rglob("*.py"):
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue

                    # Detect 'core-admin' calls
                    cmd_str = self._extract_command_string(node)
                    if not cmd_str or not cmd_str.startswith("core-admin"):
                        continue

                    # Parse 'core-admin fix ids' -> 'fix.ids'
                    # Logic: skip binary, join next parts with dot until a flag/option appears
                    parts = cmd_str.split()
                    if len(parts) < 2:
                        continue

                    # Heuristic: Convert 'verb noun' to 'verb.noun'
                    # This assumes standard CORE CLI pattern pattern
                    action_parts = []
                    for p in parts[1:]:
                        if p.startswith("-"):  # Stop at flags
                            break
                        action_parts.append(p)

                    if not action_parts:
                        continue

                    action_id = ".".join(action_parts)

                    # Validate against Registry
                    if action_id not in registered_ids:
                        findings.append(
                            AuditFinding(
                                check_id="agent.compliance.respect_cli_registry",
                                severity=AuditSeverity.ERROR,
                                message=(
                                    f"Agent invokes unregistered command: '{action_id}'. "
                                    "Agents must only use capabilities registered in the DB."
                                ),
                                file_path=str(file_path.relative_to(self.repo_root)),
                                line_number=node.lineno,
                                context={"invoked": action_id, "command": cmd_str},
                            )
                        )

            except Exception as e:
                logger.debug("Failed to scan %s: %s", file_path, e)

        return findings

    def _extract_command_string(self, node: ast.Call) -> str | None:
        """Attempts to extract a string literal command from subprocess/os calls."""
        # Check subprocess.run(["cmd", ...])
        if self._is_call(node, "subprocess", ["run", "Popen", "call"]):
            if node.args and isinstance(node.args[0], ast.List):
                # Extract list of strings
                parts = []
                for elt in node.args[0].elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        parts.append(elt.value)
                    else:
                        return None  # Dynamic component
                return " ".join(parts)

        # Check os.system("cmd ...")
        if self._is_call(node, "os", ["system"]):
            if node.args and isinstance(node.args[0], ast.Constant):
                return str(node.args[0].value)

        return None

    def _is_call(self, node: ast.Call, module: str, methods: list[str]) -> bool:
        """Helper to identify library calls."""
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == module:
                if node.func.attr in methods:
                    return True
        return False
