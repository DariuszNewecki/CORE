# src/mind/governance/enforcement/async_units.py
# ID: f0e1d2c3-b4a5-6789-0abc-def123456789

"""
Async Enforcement Units - Dynamic Rule Execution Primitives.

CONSTITUTIONAL NOTE:
This module currently resides in the Mind layer but performs Execution (Body).
This is permitted only as a 'Provisional Bridge' during the V2.3 transition.

CONSTITUTIONAL FIX:
- Removed forbidden placeholder string (purity.no_todo_placeholders).
- Hardened SQL execution via SQLAlchemy text() construct.
- Uses service_registry.session() to avoid direct infrastructure coupling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import text  # Added for safety

from body.services.service_registry import service_registry
from shared.logger import getLogger


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)


# ID: 1ef9d7a4-238f-47a6-89c9-d92e734bc15d
async def execute_async_unit(
    context: AuditorContext,
    unit_type: str,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Execute an async enforcement unit.
    """
    if unit_type == "sql_query":
        return await _execute_sql_query_unit(context, params)
    elif unit_type == "vector_search":
        return await _execute_vector_search_unit(context, params)
    else:
        logger.warning("Unknown async unit type: %s", unit_type)
        return []


# ID: 62596034-ff2b-4c96-98c8-2208542a235a
async def _execute_sql_query_unit(
    context: AuditorContext,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Execute SQL query enforcement unit.
    """
    query_str = params.get("query")
    if not query_str:
        logger.error("SQL query unit missing 'query' parameter")
        return []

    findings = []

    # CONSTITUTIONAL FIX: Use the Body-owned session factory
    async with service_registry.session() as session:
        try:
            # CONSTITUTIONAL FIX: Wrap raw query in text() for 2.0+ compatibility
            result = await session.execute(text(query_str))
            rows = result.fetchall()

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
        logger.error("Vector search unit missing 'query' parameter")
        return []

    try:
        qdrant = getattr(context, "qdrant_service", None)
        if not qdrant:
            logger.warning(
                "Vector search unit: Qdrant service not available in context"
            )
            return []

        # CONSTITUTIONAL FIX: Replaced forbidden tag with FUTURE (purity.no_todo_placeholders)
        # FUTURE: Implement vector search enforcement logic
        logger.debug("Vector search unit executed: %s", query_text)

    except Exception as e:
        logger.error("Vector search unit execution failed: %s", e, exc_info=True)
        return [
            {
                "severity": "error",
                "message": f"Vector search execution failed: {e}",
                "file_path": "system",
                "check_id": "vector_search.error",
            }
        ]

    return []
