# src/mind/governance/enforcement/async_units.py

"""
Async Enforcement Units - Dynamic Rule Execution Primitives.

CONSTITUTIONAL FIX:
- Uses service_registry.session() instead of get_session()
- Mind layer receives session factory from Body layer
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from body.services.service_registry import service_registry
from shared.logger import getLogger


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)


# ID: f0e1d2c3-b4a5-6789-0abc-def123456789
async def execute_async_unit(
    context: AuditorContext,
    unit_type: str,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Execute an async enforcement unit.

    Args:
        context: Auditor context with policies and knowledge graph
        unit_type: Type of unit to execute (e.g., 'sql_query', 'vector_search')
        params: Unit-specific parameters

    Returns:
        List of findings/violations detected by the unit
    """
    if unit_type == "sql_query":
        return await _execute_sql_query_unit(context, params)
    elif unit_type == "vector_search":
        return await _execute_vector_search_unit(context, params)
    else:
        logger.warning("Unknown async unit type: %s", unit_type)
        return []


# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
async def _execute_sql_query_unit(
    context: AuditorContext,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Execute SQL query enforcement unit.

    Constitutional Note:
    Uses service_registry for session access - Mind layer doesn't create sessions.
    """
    query = params.get("query")
    if not query:
        logger.error("SQL query unit missing 'query' parameter")
        return []

    findings = []

    # CONSTITUTIONAL FIX: Use service_registry.session() instead of get_session()
    async with service_registry.session() as session:
        try:
            result = await session.execute(query)
            rows = result.fetchall()

            # Process results based on unit configuration
            for row in rows:
                findings.append(
                    {
                        "severity": params.get("severity", "error"),
                        "message": params.get(
                            "message_template", "Violation detected"
                        ).format(**dict(row._mapping)),
                        "file_path": row._mapping.get("file_path", "unknown"),
                        "check_id": params.get("check_id", "sql_query"),
                    }
                )

        except Exception as e:
            logger.error("SQL query unit execution failed: %s", e, exc_info=True)
            findings.append(
                {
                    "severity": "error",
                    "message": f"SQL query execution failed: {e}",
                    "file_path": "system",
                    "check_id": "sql_query.error",
                }
            )

    return findings


# ID: b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e
async def _execute_vector_search_unit(
    context: AuditorContext,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Execute vector search enforcement unit.

    Constitutional Note:
    Uses context.qdrant_service injected by auditor (JIT pattern).
    """
    query_text = params.get("query")
    if not query_text:
        logger.error("Vector search unit missing 'query' parameter")
        return []

    findings = []

    try:
        # Qdrant service injected by auditor during JIT setup
        qdrant = getattr(context, "qdrant_service", None)
        if not qdrant:
            logger.warning(
                "Vector search unit: Qdrant service not available in context"
            )
            return []

        # TODO: Implement vector search enforcement logic
        # This is a placeholder for future vector-based constitutional checks
        logger.debug("Vector search unit executed: %s", query_text)

    except Exception as e:
        logger.error("Vector search unit execution failed: %s", e, exc_info=True)
        findings.append(
            {
                "severity": "error",
                "message": f"Vector search execution failed: {e}",
                "file_path": "system",
                "check_id": "vector_search.error",
            }
        )

    return findings
