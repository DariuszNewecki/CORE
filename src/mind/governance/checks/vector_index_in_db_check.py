# src/mind/governance/checks/vector_index_in_db_check.py
"""
Enforces db.vector_index_in_db: All vector indexes must be registered in DB.
"""

from __future__ import annotations

import ast
from pathlib import Path

from mind.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: ecf99ad0-883b-42e3-bbec-898ff40a3cc4
class VectorIndexInDbCheck(BaseCheck):
    policy_rule_ids = ["db.vector_index_in_db"]

    # ID: 63b6cc1c-1573-4fff-bdb4-2798c4610ae8
    def execute(self) -> list[AuditFinding]:
        findings = []

        # Load vector indexes from DB
        try:
            from services.database.session_manager import get_session

            async def _get_indexes():
                async with get_session() as db:
                    result = await db.execute("SELECT name FROM vector_indexes")
                    return {row[0] for row in result.fetchall()}

            import asyncio

            registered = asyncio.run(_get_indexes())
        except Exception:
            registered = set()

        # Scan code for vector index usage
        for file_path in self.context.python_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if (
                            isinstance(node.func, ast.Attribute)
                            and node.func.attr == "get_vector_index"
                        ):
                            if node.args and isinstance(node.args[0], ast.Str):
                                index = node.args[0].s
                                if index not in registered:
                                    findings.append(
                                        self._finding(file_path, node.lineno, index)
                                    )
            except Exception:
                pass

        return findings

    def _finding(self, file_path: Path, line: int, index: str) -> AuditFinding:
        return AuditFinding(
            check_id="db.vector_index_in_db",
            severity=AuditSeverity.ERROR,
            message=f"Unregistered vector index: `{index}`. Run `fix db-vector-index`.",
            file_path=str(file_path.relative_to(self.repo_root)),
            line_number=line,
        )
