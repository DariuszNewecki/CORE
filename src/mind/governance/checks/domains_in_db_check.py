# src/mind/governance/checks/domains_in_db_check.py
"""
Enforces db.domains_in_db: All domains must be registered in DB.
"""

from __future__ import annotations

import ast
from pathlib import Path

from shared.models import AuditFinding, AuditSeverity

from mind.governance.checks.base_check import BaseCheck


# ID: i9j0k1l2-m3n4-4o5p-6q7r-8s9t0u1v2w3x
# ID: 77e5c60a-7802-4d64-be11-c1bc20cde9d9
class DomainsInDbCheck(BaseCheck):
    policy_rule_ids = ["db.domains_in_db"]

    # ID: 73e385d6-375d-440e-b8f3-b9b4abe78c25
    def execute(self) -> list[AuditFinding]:
        findings = []

        # Load domains from DB
        try:
            from services.database.session_manager import get_session

            async def _get_domains():
                async with get_session() as db:
                    result = await db.execute("SELECT name FROM domains")
                    return {row[0] for row in result.fetchall()}

            import asyncio

            registered = asyncio.run(_get_domains())
        except Exception:
            registered = set()

        # Scan code for domain usage
        for file_path in self.context.python_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if (
                            isinstance(node.func, ast.Attribute)
                            and node.func.attr == "get_domain"
                        ):
                            if node.args and isinstance(node.args[0], ast.Str):
                                domain = node.args[0].s
                                if domain not in registered:
                                    findings.append(
                                        self._finding(file_path, node.lineno, domain)
                                    )
            except Exception:
                pass

        return findings

    def _finding(self, file_path: Path, line: int, domain: str) -> AuditFinding:
        return AuditFinding(
            check_id="db.domains_in_db",
            severity=AuditSeverity.ERROR,
            message=f"Unregistered domain: `{domain}`. Run `fix db-domains`.",
            file_path=str(file_path.relative_to(self.repo_root)),
            line_number=line,
        )
