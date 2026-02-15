# src/body/services/database_service.py
"""
Database Service - Body Layer

CONSTITUTIONAL FIX: Infrastructure wrapper for database access

This service provides database operations for Will layer.
Will layer must NEVER import get_session or AsyncSession directly.
All database access goes through this Body service.

Constitutional Compliance:
- Body layer: Wraps infrastructure primitives
- Provides high-level operations for Will
- Manages session lifecycle internally
- Will receives this service, never creates sessions

Architecture:
- Mind: Defines what data exists (.intent/ schemas)
- Body: Executes database operations (this file)
- Will: Orchestrates using Body services (never touches infrastructure)
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select

from shared.infrastructure.database.models import CognitiveRole, LlmResource
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: fcd07157-1701-459c-ac91-902d251ee471
# ID: 78cbd4a9-32a2-49cd-84dd-4f401daa8df3
class DatabaseService:
    """
    Body layer service for database operations.

    CONSTITUTIONAL ROLE:
    - Body layer: Infrastructure wrapper
    - Provides database operations without exposing sessions
    - Will layer uses this service, never imports get_session
    - Manages session lifecycle internally

    This service encapsulates all database infrastructure.
    Will layer receives instances of this service and calls methods.
    """

    def __init__(self):
        """
        Initialize database service.

        Note: Does NOT take a session in constructor.
        Sessions are created per-operation to avoid lifecycle issues.
        """
        logger.debug("DatabaseService initialized")

    # ID: fe56d2c9-df6c-42c1-acef-0633db3a4392
    # ID: 872b8a2c-50ff-493a-b6ba-be62215f4c63
    async def query_roles(self) -> list[CognitiveRole]:
        """
        Query all cognitive roles from database.

        Body layer execution:
        - Creates session internally
        - Executes query
        - Closes session
        - Returns results to Will

        Returns:
            List of CognitiveRole objects
        """
        async with get_session() as session:
            result = await session.execute(select(CognitiveRole))
            roles = result.scalars().all()
            logger.debug("Queried %d cognitive roles", len(roles))
            return list(roles)

    # ID: 8f054637-4af9-43a3-a483-cf641288ac65
    # ID: 8b644d68-426f-4bfa-a866-5bdbbe8ee7fe
    async def query_resources(self) -> list[LlmResource]:
        """
        Query all LLM resources from database.

        Body layer execution:
        - Creates session internally
        - Executes query
        - Closes session
        - Returns results to Will

        Returns:
            List of LlmResource objects
        """
        async with get_session() as session:
            result = await session.execute(select(LlmResource))
            resources = result.scalars().all()
            logger.debug("Queried %d LLM resources", len(resources))
            return list(resources)

    # ID: 2079a7bc-55d4-4c41-88b4-592ab1be14d5
    # ID: 1e312dd0-ddf2-482f-95db-959654191557
    async def query_role_by_id(self, role_id: UUID) -> CognitiveRole | None:
        """
        Query a specific cognitive role by ID.

        Body layer execution:
        - Creates session internally
        - Executes query
        - Closes session
        - Returns result to Will

        Args:
            role_id: UUID of the role to query

        Returns:
            CognitiveRole if found, None otherwise
        """
        async with get_session() as session:
            result = await session.execute(
                select(CognitiveRole).where(CognitiveRole.id == role_id)
            )
            role = result.scalar_one_or_none()

            if role:
                # FIX: CognitiveRole.role is the attribute name, not role_name
                logger.debug("Found role: %s", role.role)
            else:
                logger.debug("Role not found: %s", role_id)

            return role

    # ID: 7696191e-fce8-43d1-a277-14209cbe61cb
    # ID: 69abb440-9af8-4107-bcee-264cec877251
    async def query_resource_by_id(self, resource_id: UUID) -> LlmResource | None:
        """
        Query a specific LLM resource by ID.

        Body layer execution:
        - Creates session internally
        - Executes query
        - Closes session
        - Returns result to Will

        Args:
            resource_id: UUID of the resource to query

        Returns:
            LlmResource if found, None otherwise
        """
        async with get_session() as session:
            result = await session.execute(
                select(LlmResource).where(LlmResource.id == resource_id)
            )
            resource = result.scalar_one_or_none()

            if resource:
                # FIX: LlmResource.name is the attribute name, not resource_name
                logger.debug("Found resource: %s", resource.name)
            else:
                logger.debug("Resource not found: %s", resource_id)

            return resource

    # ID: e55db17c-b7d0-469a-a922-32d8e9ec9bf2
    # ID: f6a7b8c9-d0e1-2f3a-4b5c-6d7e8f9a0b1c
    async def execute_query(
        self, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Execute a raw SQL query with parameters.

        Body layer execution:
        - Creates session internally
        - Executes parameterized query
        - Closes session
        - Returns results to Will

        Args:
            query: SQL query string
            params: Optional parameters for the query

        Returns:
            List of result dictionaries

        Warning:
            Use this sparingly. Prefer typed methods above.
        """
        from sqlalchemy import text

        async with get_session() as session:
            stmt = text(query)
            result = await session.execute(stmt, params or {})
            rows = [dict(row._mapping) for row in result]
            logger.debug("Executed raw query, returned %d rows", len(rows))
            return rows

    # ID: 40c35af6-f4d3-434f-beda-4f6fe663b805
    # ID: a7b8c9d0-e1f2-3a4b-5c6d-7e8f9a0b1c2d
    async def with_session(self, operation):
        """
        Execute an operation with a managed session.

        Body layer execution:
        - Creates session
        - Passes to operation callback
        - Ensures session is closed
        - Returns operation result

        This is for complex operations that need session control.

        Args:
            operation: Async callable that takes (session) and returns result

        Returns:
            Result from operation

        Example:
            async def complex_query(session):
                # Do complex multi-step operation
                return result

            result = await db_service.with_session(complex_query)
        """
        async with get_session() as session:
            return await operation(session)


# ID: 214fe663-56b8-49b1-9f8f-8811f76c2f90
# ID: 0cf303d2-3131-4d15-9b42-83d3de3c3579
def get_database_service() -> DatabaseService:
    """
    Factory function for database service.

    Returns:
        DatabaseService instance

    Usage:
        # Body layer: Create service
        db_service = get_database_service()

        # Will layer: Use service
        roles = await db_service.query_roles()
    """
    return DatabaseService()
