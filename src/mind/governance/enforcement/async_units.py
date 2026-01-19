# src/mind/governance/enforcement/async_units.py

"""Refactored logic for src/mind/governance/enforcement/async_units.py."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy import text

from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity

from .base import AsyncEnforcementMethod


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)


# ID: knowledge-ssot-enforcement
# ID: 1aea6ed5-86e9-4034-9ec9-053738e0c65f
class KnowledgeSSOTEnforcement(AsyncEnforcementMethod):
    """Verifies that operational knowledge exists in DB tables (SSOT)."""

    _SSOT_TABLES: ClassVar[list[dict[str, str]]] = [
        {
            "name": "cli_registry",
            "rule_id": "db.cli_registry_in_db",
            "table": "core.cli_commands",
            "primary_key": "name",
        },
        {
            "name": "llm_resources",
            "rule_id": "db.llm_resources_in_db",
            "table": "core.llm_resources",
            "primary_key": "name",
        },
        {
            "name": "cognitive_roles",
            "rule_id": "db.cognitive_roles_in_db",
            "table": "core.cognitive_roles",
            "primary_key": "role",
        },
        {
            "name": "domains",
            "rule_id": "db.domains_in_db",
            "table": "core.domains",
            "primary_key": "key",
        },
    ]

    # ID: 94856ace-9f30-4dcf-82b6-f7919a74a7c1
    async def verify_async(
        self, context: AuditorContext, rule_data: dict[str, Any]
    ) -> list[AuditFinding]:
        findings = []
        try:
            async with get_session() as session:
                for cfg in self._SSOT_TABLES:
                    findings.extend(await self._check_table(session, cfg))
        except Exception as e:
            logger.error("Failed DB audit in KnowledgeSSOTEnforcement: %s", e)
            findings.append(
                self._create_finding(
                    f"DB SSOT audit failed (session or query error): {e}",
                    file_path="DB",
                )
            )
        return findings

    async def _check_table(self, session, cfg: dict) -> list[AuditFinding]:
        findings, table, pk, rule_id, name = (
            [],
            cfg["table"],
            cfg["primary_key"],
            cfg["rule_id"],
            cfg["name"],
        )
        try:
            count_stmt = text(f"select count(*) as n from {table}")
            res = await session.execute(count_stmt)
            if int(res.scalar_one()) == 0:
                findings.append(
                    AuditFinding(
                        check_id=rule_id,
                        severity=AuditSeverity.ERROR,
                        message=f"DB SSOT table '{table}' is empty. Operational knowledge must exist in DB.",
                        file_path="DB",
                    )
                )
                return findings

            dup_stmt = text(
                f"SELECT {pk}, COUNT(*) as cnt FROM {table} GROUP BY {pk} HAVING COUNT(*) > 1"
            )
            duplicates = (await session.execute(dup_stmt)).fetchall()
            if duplicates:
                dup_keys = [str(row[0]) for row in duplicates]
                findings.append(
                    AuditFinding(
                        check_id=rule_id,
                        severity=AuditSeverity.ERROR,
                        message=f"DB SSOT table '{table}' has duplicate primary keys: {', '.join(dup_keys)}",
                        file_path="DB",
                    )
                )
        except Exception as e:
            findings.append(
                AuditFinding(
                    check_id=rule_id,
                    severity=AuditSeverity.ERROR,
                    message=f"DB SSOT PK uniqueness check failed for '{name}': {e}",
                    file_path="DB",
                )
            )
        return findings
