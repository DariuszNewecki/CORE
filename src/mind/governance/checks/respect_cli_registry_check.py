# src/mind/governance/checks/respect_cli_registry_check.py
"""
Enforces agent.compliance.respect_cli_registry: AI must use only registered CLI commands.
"""

from __future__ import annotations

import ast
from pathlib import Path

from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity
from sqlalchemy import select

from mind.governance.checks.base_check import BaseCheck

logger = getLogger(__name__)


# ID: d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a
class RespectCliRegistryCheck(BaseCheck):
    policy_rule_ids = ["agent.compliance.respect_cli_registry"]

    # --- START OF FIX: Make _get_registered an async method ---
    async def _get_registered(self) -> set[str]:
        """Asynchronously fetches the set of registered command names from the database."""
        from services.database.models import CliCommand
        from services.database.session_manager import get_session

        async with get_session() as db:
            result = await db.execute(select(CliCommand.name))
            return {row[0] for row in result.fetchall()}

    # --- END OF FIX ---

    # --- START OF FIX: Convert the main execute method to async ---
    # ID: e67915d4-4b91-449f-b7af-f64ac3b2c72b
    async def execute(self) -> list[AuditFinding]:
        findings = []

        # Load registered CLI commands from DB
        registered = set()
        try:
            # Await the async method directly instead of using asyncio.run()
            registered = await self._get_registered()
            logger.info(
                f"Loaded {len(registered)} registered CLI commands: {sorted(registered)}"
            )
        except Exception as e:
            logger.warning(
                f"Failed to load CLI registry: {e}. Treating all commands as unregistered."
            )
        # --- END OF FIX ---

        # Look for subprocess/os.system calls (this part remains synchronous)
        for file_path in self.context.python_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue

                    cmd = None
                    # subprocess.run(['core-admin', 'fix', 'ids'])
                    if isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr
                        module_name = (
                            getattr(node.func.value, "id", "")
                            if hasattr(node.func.value, "id")
                            else ""
                        )
                        if (
                            func_name in ("run", "Popen")
                            and module_name == "subprocess"
                        ):
                            if node.args and isinstance(
                                node.args[0], (ast.List, ast.Tuple)
                            ):
                                cmd_parts = []
                                for elt in node.args[0].elts:
                                    if isinstance(elt, ast.Str):
                                        cmd_parts.append(elt.s)
                                    elif isinstance(elt, ast.Constant) and isinstance(
                                        elt.value, str
                                    ):
                                        cmd_parts.append(elt.value)
                                cmd = " ".join(cmd_parts)
                        # os.system("core-admin fix ids")
                        elif func_name == "system" and module_name == "os":
                            if node.args and isinstance(
                                node.args[0], (ast.Str, ast.Constant)
                            ):
                                arg = node.args[0]
                                cmd = arg.s if hasattr(arg, "s") else arg.value

                    if cmd and cmd.startswith("core-admin"):
                        parts = cmd.split()
                        subcommand = ".".join(parts[1:3]) if len(parts) > 2 else ""
                        if subcommand and subcommand not in registered:
                            findings.append(self._finding(file_path, node.lineno, cmd))
            except Exception as e:
                logger.debug("Failed to parse {file_path}: %s", e)

        return findings

    def _finding(self, file_path: Path, line: int, cmd: str) -> AuditFinding:
        return AuditFinding(
            check_id="agent.compliance.respect_cli_registry",
            severity=AuditSeverity.ERROR,
            message=f"Unregistered CLI command: `{cmd}`. Run `fix db-registry` to register.",
            file_path=str(file_path.relative_to(self.repo_root)),
            line_number=line,
        )
