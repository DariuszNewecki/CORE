# src/mind/governance/enforcement/async_units.py
# ID: f0e1d2c3-b4a5-6789-0abc-def123456789

"""
Async Enforcement Units - Dynamic Rule Execution Primitives.

CONSTITUTIONAL HARDENING:
Now uses Protocols to avoid Mind -> Body leakage (P2.2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy import text

from shared.logger import getLogger
from shared.models import AuditFinding

from .base import AsyncEnforcementMethod


logger = getLogger(__name__)

if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext
    from shared.protocols.knowledge import SessionProviderProtocol


# ID: 4b847bc4-578d-4789-ac5e-6db79848f5f2
class KnowledgeSSOTEnforcement(AsyncEnforcementMethod):
    """
    Verifies operational SSOT tables exist, are non-empty, and have unique PKs.

    Compatibility note:
    The public API historically exposed this class from
    `mind.governance.enforcement.async_units`.
    """

    _SSOT_TABLES: ClassVar[list[dict[str, str]]] = [
        {
            "name": "CLI commands",
            "rule_id": "db.cli_registry_in_db",
            "table": "core.cli_commands",
            "primary_key": "name",
        },
        {
            "name": "LLM resources",
            "rule_id": "db.llm_resources_in_db",
            "table": "core.llm_resources",
            "primary_key": "name",
        },
        {
            "name": "Cognitive roles",
            "rule_id": "db.cognitive_roles_in_db",
            "table": "core.cognitive_roles",
            "primary_key": "role",
        },
        {
            "name": "Domains",
            "rule_id": "db.domains_in_db",
            "table": "core.domains",
            "primary_key": "key",
        },
    ]

    # ID: 109e933d-708a-400c-b7a1-bcb25ae13aaf
    async def verify_async(
        self, context: AuditorContext, rule_data: dict[str, Any]
    ) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        tables_to_check = self._tables_for_rule()

        try:
            # Local import keeps async unit import path lightweight.
            from shared.infrastructure.database.session_manager import get_session

            async with get_session() as session:
                for table_cfg in tables_to_check:
                    findings.extend(
                        await self._check_table(
                            session=session,
                            table_name=table_cfg["table"],
                            primary_key=table_cfg["primary_key"],
                        )
                    )
        except Exception as e:
            findings.append(
                self._create_finding(
                    message=f"DB SSOT audit failed: {e}",
                    file_path="DB",
                )
            )

        return findings

    def _tables_for_rule(self) -> list[dict[str, str]]:
        if self.rule_id == "db.ssot_for_operational_data":
            return list(self._SSOT_TABLES)
        return [cfg for cfg in self._SSOT_TABLES if cfg["rule_id"] == self.rule_id]

    async def _check_table(
        self,
        session: Any,
        table_name: str,
        primary_key: str,
    ) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        try:
            count_result = await session.execute(
                text(f"SELECT COUNT(*) FROM {table_name}")
            )
            row_count = int(count_result.scalar_one() or 0)
        except Exception as e:
            return [
                self._create_finding(
                    message=f"DB SSOT table check failed for {table_name}: {e}",
                    file_path="DB",
                )
            ]

        if row_count == 0:
            findings.append(
                self._create_finding(
                    message=f"DB SSOT table '{table_name}' is empty.",
                    file_path="DB",
                )
            )
            return findings

        try:
            dup_result = await session.execute(
                text(
                    f"""
                    SELECT {primary_key}, COUNT(*) AS c
                    FROM {table_name}
                    GROUP BY {primary_key}
                    HAVING COUNT(*) > 1
                    """
                )
            )
            duplicates = dup_result.fetchall()
            if duplicates:
                findings.append(
                    self._create_finding(
                        message=(
                            f"DB SSOT table '{table_name}' has duplicate primary keys "
                            f"on '{primary_key}'."
                        ),
                        file_path="DB",
                    )
                )
        except Exception as e:
            findings.append(
                self._create_finding(
                    message=(
                        f"DB SSOT PK uniqueness check failed for {table_name}.{primary_key}: {e}"
                    ),
                    file_path="DB",
                )
            )

        return findings


# ID: 1ef9d7a4-238f-47a6-89c9-d92e734bc15d
async def execute_async_unit(
    context: AuditorContext,
    unit_type: str,
    params: dict[str, Any],
    session_provider: SessionProviderProtocol | None = None,
) -> list[dict[str, Any]]:
    """
    Execute an async enforcement unit.
    """

    if unit_type == "sql_query":
        # Pass provider to avoid importing service_registry (P2.2)
        return await _execute_sql_query_unit(session_provider, params)

    if unit_type == "vector_search":
        return await _execute_vector_search_unit(context, params)

    logger.warning("Unknown async unit type: %s", unit_type)
    return []


# ID: 62596034-ff2b-4c96-98c8-2208542a235a
async def _execute_sql_query_unit(
    provider: SessionProviderProtocol | None,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Execute SQL query enforcement unit via injected SessionProviderProtocol.
    """

    if not provider:
        return [
            {
                "severity": "error",
                "message": "No session provider available",
                "file_path": "system",
            }
        ]

    query_str = params.get("query")
    if not query_str:
        return []

    findings: list[dict[str, Any]] = []

    async with provider.session() as session:
        try:
            result = await session.execute(text(query_str))
            rows = result.fetchall()

            for row in rows:
                row_mapping = dict(row._mapping)

                findings.append(
                    {
                        "severity": params.get("severity", "error"),
                        "message": params.get(
                            "message_template",
                            "Violation detected",
                        ).format(**row_mapping),
                        "file_path": row_mapping.get("file_path", "unknown"),
                        "check_id": params.get("check_id", "sql_query"),
                    }
                )

        except Exception as e:
            findings.append(
                {
                    "severity": "error",
                    "message": f"SQL query execution failed: {e}",
                    "file_path": "system",
                    "check_id": "sql_query.error",
                }
            )

    return findings


# ID: dda351f2-d2ae-4097-b6d3-0a0837841b72
async def _execute_vector_search_unit(
    context: AuditorContext,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Execute vector search enforcement unit.
    """

    query_text = params.get("query")
    if not query_text:
        return []

    try:
        qdrant = getattr(context, "qdrant_service", None)
        if not qdrant:
            return []

        # FUTURE: Implement vector search enforcement logic
        return []

    except Exception as e:
        return [
            {
                "severity": "error",
                "message": f"Vector search execution failed: {e}",
                "file_path": "system",
                "check_id": "vector_search.error",
            }
        ]
