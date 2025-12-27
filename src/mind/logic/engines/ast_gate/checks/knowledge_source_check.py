# src/mind/logic/engines/ast_gate/checks/knowledge_source_check.py

"""
Ensures that operational knowledge SSOT exists in the Database and is usable.

Why:
- YAML-based registries are deprecated.
- DB is the authoritative runtime source of truth.

This check intentionally avoids referencing legacy YAML artifacts.
Enforces data_governance policy (Knowledge Integrity).

Ref: .intent/charter/standards/data/governance.json
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from sqlalchemy import text

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

GOVERNANCE_POLICY = Path(".intent/charter/standards/data/governance.json")

# DB SSOT tables that must exist and contain records.
# These replace deprecated YAML sources.
_SSOT_TABLES = [
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


# ID: knowledge-ssot-enforcement
# ID: 1aea6ed5-86e9-4034-9ec9-053738e0c65f
class KnowledgeSSOTEnforcement(EnforcementMethod):
    """
    Verifies that operational knowledge exists in DB tables (SSOT).
    Checks table existence, row counts, and primary key uniqueness.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: bf759401-01f8-41b3-854b-77d20331c002
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        """
        Async verification method - checks DB tables.
        Note: This breaks the sync pattern but is necessary for DB access.
        """
        # This is an async check, so we need to handle it specially
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context
                logger.warning(
                    "Cannot run KnowledgeSourceCheck in nested async context"
                )
                return []
            else:
                return loop.run_until_complete(self._verify_async(context, rule_data))
        except RuntimeError:
            # No event loop available
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self._verify_async(context, rule_data))
            finally:
                loop.close()

    async def _verify_async(
        self, context: AuditorContext, rule_data: dict[str, Any]
    ) -> list[AuditFinding]:
        findings = []

        try:
            async with get_session() as session:
                for cfg in _SSOT_TABLES:
                    findings.extend(await self._check_table(session, cfg))
        except Exception as e:
            logger.error("Failed DB audit in KnowledgeSourceCheck: %s", e)
            findings.append(
                AuditFinding(
                    check_id=self.rule_id,
                    severity=self.severity,
                    message=f"DB SSOT audit failed (session or query error): {e}",
                    file_path="DB",
                )
            )

        return findings

    async def _check_table(self, session, cfg: dict) -> list[AuditFinding]:
        findings = []
        table = cfg["table"]
        pk = cfg["primary_key"]
        rule_id = cfg["rule_id"]
        name = cfg["name"]

        # 1) Basic table presence + row count
        try:
            count_stmt = text(f"select count(*) as n from {table}")
            result = await session.execute(count_stmt)
            row_count = int(result.scalar_one())
        except Exception as e:
            findings.append(
                AuditFinding(
                    check_id=rule_id,
                    severity=AuditSeverity.ERROR,
                    message=f"DB SSOT table check failed for '{name}' ({table}): {e}",
                    file_path="DB",
                )
            )
            return findings

        if row_count == 0:
            findings.append(
                AuditFinding(
                    check_id=rule_id,
                    severity=AuditSeverity.ERROR,
                    message=(
                        f"DB SSOT table '{table}' is empty. "
                        "Operational knowledge is missing from the Database (SSOT)."
                    ),
                    file_path="DB",
                    context={"table": table, "rows": row_count},
                )
            )
            return findings

        # 2) Primary key uniqueness sanity check (detect split/duplication)
        try:
            dup_stmt = text(
                f"""
                select {pk} as key, count(*) as c
                from {table}
                group by {pk}
                having count(*) > 1
                limit 10
                """
            )
            dup_res = await session.execute(dup_stmt)
            dups = [{"key": r.key, "count": int(r.c)} for r in dup_res.fetchall()]
        except Exception as e:
            findings.append(
                AuditFinding(
                    check_id=rule_id,
                    severity=AuditSeverity.WARNING,
                    message=f"DB SSOT uniqueness check failed for '{table}.{pk}': {e}",
                    file_path="DB",
                )
            )
            return findings

        if dups:
            findings.append(
                AuditFinding(
                    check_id=rule_id,
                    severity=AuditSeverity.ERROR,
                    message=(
                        f"DB SSOT integrity violation: duplicate primary keys detected in {table}.{pk}. "
                        "Database must represent a consistent SSOT."
                    ),
                    file_path="DB",
                    context={"table": table, "primary_key": pk, "duplicates": dups},
                )
            )

        return findings


# ID: 81d6e8ed-a6f6-444c-acda-9064896c5111
class KnowledgeSourceCheck(RuleEnforcementCheck):
    """
    Ensures that operational knowledge SSOT exists in the Database and is usable.

    Why:
    - YAML-based registries are deprecated.
    - DB is the authoritative runtime source of truth.

    Ref: .intent/charter/standards/data/governance.json
    """

    policy_rule_ids: ClassVar[list[str]] = [
        "db.ssot_for_operational_data",
        "db.cli_registry_in_db",
        "db.llm_resources_in_db",
        "db.cognitive_roles_in_db",
        "db.domains_in_db",
    ]

    policy_file: ClassVar[Path] = GOVERNANCE_POLICY

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        KnowledgeSSOTEnforcement(rule_id="db.ssot_for_operational_data"),
        KnowledgeSSOTEnforcement(rule_id="db.cli_registry_in_db"),
        KnowledgeSSOTEnforcement(rule_id="db.llm_resources_in_db"),
        KnowledgeSSOTEnforcement(rule_id="db.cognitive_roles_in_db"),
        KnowledgeSSOTEnforcement(rule_id="db.domains_in_db"),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
