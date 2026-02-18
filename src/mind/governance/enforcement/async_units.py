# src/mind/governance/enforcement/async_units.py
# ID: f0e1d2c3-b4a5-6789-0abc-def123456789

"""
Async Enforcement Units - Dynamic Rule Execution Primitives.

CONSTITUTIONAL HARDENING:
Now uses Protocols to avoid Mind -> Body leakage (P2.2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from shared.logger import getLogger


logger = getLogger(__name__)

if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext
    from shared.protocols.knowledge import SessionProviderProtocol


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
